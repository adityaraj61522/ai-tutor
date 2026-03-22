"""
FAISS-backed vector store powered by Google Gemini embeddings.

Responsibilities:
  - Chunk raw text with LangChain's RecursiveCharacterTextSplitter
  - Embed chunks using the Gemini embedding API
  - Persist / reload the FAISS index to/from disk
  - Expose similarity search and retrieval-augmented generation (RAG) query

Typical usage::

    vs = VectorStore(google_api_key="...")
    vs.create_vector_store_from_text(my_text)
    results = vs.search_similar("some topic", k=5)
    answer  = vs.query_with_sources("explain X in 60 words")
"""

import logging
import os
import time
from typing import Any, Dict, List, Tuple

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Primary Gemini embedding model.  If it fails, the list below is tried in order.
_PRIMARY_EMBED_MODEL = "gemini-embedding-001"
_PRIMARY_EMBED_API_VER = "v1beta"

# Fallback (model_name, api_version) pairs tried when the primary model fails.
# Each entry MUST be a 2-tuple so the `for mname, apiver in` loop unpacks correctly.
_FALLBACK_EMBED_MODELS: List[Tuple[str, str]] = [
    ("models/text-embedding-004", "v1beta"),
]

# LLM used for RAG generation
_LLM_MODEL = "gemini-2.5-flash"

# Seconds to wait after embedding creation to avoid hitting rate limits
_RATE_LIMIT_SLEEP = 2


# ---------------------------------------------------------------------------
# VectorStore class
# ---------------------------------------------------------------------------


class VectorStore:
    """
    FAISS vector store backed by Google Gemini embeddings and an LLM for RAG.

    The store is lazily populated: call create_vector_store_from_text() before
    using search_similar() or query_with_sources().
    """

    def __init__(
        self,
        google_api_key: str | None = None,
        pickle_file: str = "faiss_store",
    ) -> None:
        """
        Initialise embeddings, LLM, and text splitter.

        Args:
            google_api_key: Google API key.  Falls back to the GOOGLE_API_KEY
                            environment variable if not supplied.
            pickle_file:    Directory name for FAISS save_local / load_local.
                            A ".pkl" suffix is stripped automatically for
                            compatibility with the FAISS native serialisation.

        Raises:
            ValueError: If no API key is available.
        """
        if google_api_key is None:
            google_api_key = os.environ.get("GOOGLE_API_KEY")

        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        # Store key for use in embedding fallback attempts
        self.google_api_key = google_api_key

        # Primary embedding model
        logger.info(
            "Initialising embeddings with model '%s' (api_version=%s).",
            _PRIMARY_EMBED_MODEL,
            _PRIMARY_EMBED_API_VER,
        )
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=_PRIMARY_EMBED_MODEL,
            google_api_key=google_api_key,
            model_kwargs={"api_version": _PRIMARY_EMBED_API_VER},
        )

        # LLM used for RAG answer generation
        logger.info("Initialising LLM with model '%s'.", _LLM_MODEL)
        self.llm = ChatGoogleGenerativeAI(
            model=_LLM_MODEL,
            temperature=0.9,
            google_api_key=google_api_key,
            model_kwargs={"api_version": "v1"},
        )

        self.vectorstore: FAISS | None = None

        # Strip ".pkl" so the path works with FAISS's directory-based serialisation
        self.pickle_file = pickle_file.removesuffix(".pkl")

        # Splitter configuration: prefer paragraph > line > sentence > comma breaks
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", ","],
            chunk_size=1000,
        )

        logger.debug("VectorStore initialised.  FAISS index path: '%s'.", self.pickle_file)

    # ------------------------------------------------------------------
    # Text chunking utilities
    # ------------------------------------------------------------------

    def chunk_text_by_full_stops(self, text: str) -> List[str]:
        """
        Split text into sentence-level chunks on full stops.

        This is a lightweight alternative to the RecursiveCharacterTextSplitter
        when you want one chunk per sentence.

        Args:
            text: The text to split.

        Returns:
            List of non-empty sentence strings, each ending with a period.
        """
        chunks = text.split(". ")
        cleaned: List[str] = []

        for chunk in chunks:
            chunk = chunk.strip()
            if chunk:
                # Re-append the period that was consumed by split()
                if not chunk.endswith("."):
                    chunk += "."
                cleaned.append(chunk)

        logger.debug("chunk_text_by_full_stops: produced %d chunk(s).", len(cleaned))
        return cleaned

    # ------------------------------------------------------------------
    # Index creation
    # ------------------------------------------------------------------

    def create_vector_store_from_text(self, text: str) -> bool:
        """
        Build a FAISS vector store from raw text.

        Steps:
          1. Wrap the text in a LangChain Document.
          2. Split into chunks with RecursiveCharacterTextSplitter.
          3. Embed chunks using the primary Gemini embedding model,
             falling back to alternatives if the primary fails.
          4. Persist the index to disk via FAISS.save_local.

        Args:
            text: The full document text to index.

        Returns:
            True on success.

        Raises:
            Exception: If the vector store cannot be created after all fallbacks.
        """
        logger.info(
            "Creating vector store from %d characters of text.", len(text)
        )

        try:
            # 1. Wrap in a Document so the splitter keeps metadata intact
            doc = Document(page_content=text, metadata={"source": "pdf"})

            # 2. Split into chunks
            docs = self.text_splitter.split_documents([doc])
            logger.info("Text split into %d chunk(s).", len(docs))

            if not docs:
                logger.warning("Text splitter produced zero chunks – aborting.")
                return False

            # 3. Embed and build FAISS index
            try:
                logger.debug("Attempting primary embedding model '%s'.", _PRIMARY_EMBED_MODEL)
                self.vectorstore = FAISS.from_documents(docs, self.embeddings)
                logger.info("Vector store created with primary embedding model.")
            except Exception as primary_exc:
                logger.warning(
                    "Primary embedding model failed: %s.  Trying fallbacks.", primary_exc
                )
                self._try_fallback_embeddings(docs, primary_exc)

            # Brief pause to stay within API rate limits
            logger.debug("Sleeping %ds to avoid rate-limit issues.", _RATE_LIMIT_SLEEP)
            time.sleep(_RATE_LIMIT_SLEEP)

            # 4. Persist the index to disk
            self.vectorstore.save_local(self.pickle_file)
            logger.info("FAISS index saved to '%s'.", self.pickle_file)

            return True

        except Exception as exc:
            logger.exception("Failed to create vector store: %s", exc)
            raise Exception(f"Error creating vector store: {exc}") from exc

    def _try_fallback_embeddings(self, docs: List[Document], original_exc: Exception) -> None:
        """
        Try each entry in _FALLBACK_EMBED_MODELS until one succeeds.

        Updates self.embeddings and self.vectorstore on the first success.

        Args:
            docs:         The already-split Document list to embed.
            original_exc: The exception raised by the primary model
                          (re-raised if all fallbacks fail).

        Raises:
            Exception: If every fallback model also fails.
        """
        last_exc = original_exc

        for model_name, api_version in _FALLBACK_EMBED_MODELS:
            logger.debug(
                "Trying fallback embedding model '%s' (api_version=%s).",
                model_name,
                api_version,
            )
            try:
                fallback_emb = GoogleGenerativeAIEmbeddings(
                    model=model_name,
                    google_api_key=self.google_api_key,
                    model_kwargs={"api_version": api_version},
                )
                self.vectorstore = FAISS.from_documents(docs, fallback_emb)
                # Persist the working model so future calls use it
                self.embeddings = fallback_emb
                logger.info(
                    "Vector store created with fallback model '%s'.", model_name
                )
                return
            except Exception as fallback_exc:
                logger.warning(
                    "Fallback model '%s' also failed: %s", model_name, fallback_exc
                )
                last_exc = fallback_exc

        # All options exhausted
        raise Exception(
            f"All embedding models failed.  Last error: {last_exc}"
        ) from last_exc

    # ------------------------------------------------------------------
    # Similarity search
    # ------------------------------------------------------------------

    def search_similar(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        Find the top-k document chunks most similar to the query.

        Args:
            query: The natural-language search query.
            k:     Number of results to return.

        Returns:
            List of (chunk_text, similarity_score) tuples, ordered by
            descending similarity.

        Raises:
            ValueError: If the vector store has not been initialised.
            Exception:  If the similarity search fails.
        """
        if self.vectorstore is None:
            raise ValueError(
                "Vector store not initialised.  Call create_vector_store_from_text() first."
            )

        logger.info("search_similar: query='%s', k=%d.", query, k)
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            logger.debug("search_similar: returned %d result(s).", len(results))
            return [(doc.page_content, score) for doc, score in results]
        except Exception as exc:
            logger.exception("search_similar failed: %s", exc)
            raise Exception(f"Error searching vector store: {exc}") from exc

    # ------------------------------------------------------------------
    # Retrieval-augmented generation (RAG)
    # ------------------------------------------------------------------

    def query_with_sources(self, query: str) -> Dict[str, Any]:
        """
        Answer a question using retrieved context and return source snippets.

        If the in-memory vector store is None, the method attempts to reload
        the previously persisted FAISS index from disk.

        Args:
            query: The question to answer.

        Returns:
            A dict with:
                - "answer"  (str)  : LLM-generated answer.
                - "sources" (list) : Up to 5 source dicts, each containing
                                      "content" (first 200 chars) and "metadata".

        Raises:
            ValueError: If the vector store is not available (neither
                        in-memory nor on disk).
            Exception:  If retrieval or LLM inference fails.
        """
        # Lazy-load from disk if not already in memory
        if self.vectorstore is None:
            if os.path.exists(self.pickle_file):
                logger.info(
                    "query_with_sources: loading vector store from disk ('%s').",
                    self.pickle_file,
                )
                self.vectorstore = FAISS.load_local(
                    self.pickle_file,
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
            else:
                raise ValueError(
                    "Vector store not initialised and no saved index found at "
                    f"'{self.pickle_file}'."
                )

        logger.info("query_with_sources: query='%s'.", query)

        try:
            # Retrieve the most relevant chunks
            retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
            relevant_docs = retriever.invoke(query)
            logger.debug(
                "query_with_sources: retrieved %d document(s).", len(relevant_docs)
            )

            # Concatenate chunk texts as LLM context
            context = "\n\n".join(doc.page_content for doc in relevant_docs)

            # Build a simple RAG prompt
            prompt = ChatPromptTemplate.from_template(
                "You are a helpful tutor. Answer the following question based on "
                "the provided context.\n\n"
                "Context:\n{context}\n\n"
                "Question: {question}\n\n"
                "Answer:"
            )

            # Pipe prompt → LLM (LangChain Expression Language)
            chain = prompt | self.llm
            result = chain.invoke({"context": context, "question": query})

            # Extract plain-text answer regardless of return type
            answer = result.content if hasattr(result, "content") else str(result)
            logger.debug(
                "query_with_sources: answer generated (%d chars).", len(answer)
            )

            return {
                "answer": answer,
                "sources": [
                    {
                        "content": doc.page_content[:200],  # Snippet for display
                        "metadata": doc.metadata,
                    }
                    for doc in relevant_docs
                ],
            }

        except Exception as exc:
            logger.exception("query_with_sources failed: %s", exc)
            raise Exception(f"Error querying vector store: {exc}") from exc

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def load_index(self) -> bool:
        """
        Load a previously persisted FAISS index from disk into memory.

        Returns:
            True if the index was found and loaded, False otherwise.
        """
        if os.path.exists(self.pickle_file):
            logger.info("Loading FAISS index from '%s'.", self.pickle_file)
            self.vectorstore = FAISS.load_local(
                self.pickle_file,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
            return True

        logger.warning("load_index: path '%s' does not exist.", self.pickle_file)
        return False

    def get_index_info(self) -> Dict[str, Any]:
        """
        Return a status summary for the current vector store.

        Returns:
            Dict with "status" key, plus additional fields when initialised.
        """
        if self.vectorstore is None:
            return {"status": "not_initialized"}

        return {
            "status": "initialized",
            "index_path": self.pickle_file,
            "type": type(self.vectorstore).__name__,
        }
