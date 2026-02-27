import os
import pickle
import time
from typing import List, Dict, Any, Tuple
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate


class VectorStore:
    """Vector store for managing embeddings and similarity search using FAISS and OpenAI"""
    
    def __init__(self, google_api_key: str = None, pickle_file: str = "faiss_store.pkl"):
        """Initialize the vector store with Google Gemini embeddings"""
        if google_api_key is None:
            google_api_key = os.environ.get("GOOGLE_API_KEY")
        
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        # Keep the key around for fallback attempts
        self.google_api_key = google_api_key
        
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=google_api_key,
            model_kwargs={"api_version": "v1"}
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.9,
            google_api_key=google_api_key,
            model_kwargs={"api_version": "v1"}
        )
        self.vectorstore = None
        self.pickle_file = pickle_file
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", ","],
            chunk_size=1000
        )
    
    def chunk_text_by_full_stops(self, text: str) -> List[str]:
        """
        Split text into chunks by full stops (periods)
        
        Args:
            text: The text to chunk
            
        Returns:
            List of text chunks
        """
        # Split by period followed by space or newline
        chunks = text.split(". ")
        
        # Clean up chunks and filter empty ones
        cleaned_chunks = []
        for chunk in chunks:
            chunk = chunk.strip()
            if chunk:
                # Re-add period if it was removed
                if not chunk.endswith("."):
                    chunk += "."
                cleaned_chunks.append(chunk)
        
        return cleaned_chunks
    
    def create_vector_store_from_text(self, text: str) -> bool:
        """
        Create FAISS vector store from raw text using RecursiveCharacterTextSplitter
        
        Args:
            text: The text to create embeddings for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create Document objects from text
            doc = Document(page_content=text, metadata={"source": "pdf"})
            
            # Split documents using RecursiveCharacterTextSplitter
            docs = self.text_splitter.split_documents([doc])
            
            if not docs or len(docs) == 0:
                return False
            
            # Create FAISS vector store from documents (try current embeddings, fallback if necessary)
            try:
                self.vectorstore = FAISS.from_documents(docs, self.embeddings)
            except Exception as e_inner:
                err_str = str(e_inner)
                # Try a set of fallback embedding models and API versions
                fallback_models = [
                    "models/text-embedding-004",
                ]
                last_exc = e_inner
                created = False
                for mname, apiver in fallback_models:
                    try:
                        emb = GoogleGenerativeAIEmbeddings(
                            model=mname,
                            google_api_key=self.google_api_key,
                            model_kwargs={"api_version": apiver}
                        )
                        self.vectorstore = FAISS.from_documents(docs, emb)
                        # Save working embeddings
                        self.embeddings = emb
                        created = True
                        break
                    except Exception as e2:
                        last_exc = e2
                        continue

                if not created:
                    raise Exception(f"Error creating vector store: {err_str}") from last_exc

            # Wait a moment to avoid rate limiting
            time.sleep(2)

            # Save to pickle file
            with open(self.pickle_file, "wb") as f:
                pickle.dump(self.vectorstore, f)

            return True
        
        except Exception as e:
            raise Exception(f"Error creating vector store: {str(e)}")
    
    def create_embeddings(self, chunks: List[str]):
        """Deprecated: Use create_vector_store_from_text instead"""
        pass
    
    def build_index(self, hits: int = 128):
        """Deprecated: Use create_vector_store_from_text instead"""
        pass
    
    def add_documents(self, chunks: List[str]):
        """Deprecated: Use create_vector_store_from_text instead"""
        pass
    
    def search_similar(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        Search for similar chunks to a query
        
        Args:
            query: The search query
            k: Number of results to return
            
        Returns:
            List of tuples (chunk, similarity_score)
        """
        if self.vectorstore is None:
            raise ValueError("Vector store not initialized. Call create_vector_store_from_text first.")
        
        # Search with similarity scores
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            return [(doc.page_content, score) for doc, score in results]
        except Exception as e:
            raise Exception(f"Error searching vector store: {str(e)}")
    
    def query_with_sources(self, query: str) -> Dict[str, Any]:
        """
        Query the vector store with sources using modern LangChain API
        
        Args:
            query: The question to query
            
        Returns:
            Dictionary with answer and sources
        """
        if self.vectorstore is None:
            # Try to load from pickle file
            if os.path.exists(self.pickle_file):
                with open(self.pickle_file, "rb") as f:
                    self.vectorstore = pickle.load(f)
            else:
                raise ValueError("Vector store not initialized and pickle file not found")
        
        try:
            # Get retriever from vectorstore
            retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
            
            # Retrieve relevant documents
            relevant_docs = retriever.invoke(query)
            
            # Prepare context from retrieved documents
            context = "\n\n".join([doc.page_content for doc in relevant_docs])
            
            # Create prompt template
            prompt = ChatPromptTemplate.from_template(
                "You are a helpful tutor. Answer the following question based on the provided context:\n\n"
                "Context:\n{context}\n\n"
                "Question: {question}\n\n"
                "Answer:"
            )
            
            # Create chain by piping prompt to LLM
            chain = prompt | self.llm
            
            # Invoke the chain
            result = chain.invoke({
                "context": context,
                "question": query
            })
            
            # Extract answer text
            answer = result.content if hasattr(result, 'content') else str(result)
            
            # Return result with sources
            return {
                "answer": answer,
                "sources": [
                    {
                        "content": doc.page_content[:200],  # First 200 chars
                        "metadata": doc.metadata
                    }
                    for doc in relevant_docs
                ]
            }
        
        except Exception as e:
            raise Exception(f"Error querying vector store: {str(e)}")
    
    def load_index(self):
        """Load FAISS index from pickle file"""
        if os.path.exists(self.pickle_file):
            with open(self.pickle_file, "rb") as f:
                self.vectorstore = pickle.load(f)
            return True
        return False
    
    def get_index_info(self) -> Dict:
        """Get information about the current vector store"""
        if self.vectorstore is None:
            return {"status": "not_initialized"}
        
        return {
            "status": "initialized",
            "pickle_file": self.pickle_file,
            "type": type(self.vectorstore).__name__
        }
