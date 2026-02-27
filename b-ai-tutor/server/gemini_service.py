import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage


class GeminiService:
    """Service for interacting with Google Gemini 2.5 Flash model via LangChain"""
    
    def __init__(self):
        """Initialize the Gemini service with API key from environment"""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.7
        )
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate a response from the Gemini model
        
        Args:
            prompt: The user prompt/message
            system_prompt: Optional system prompt to set context
            
        Returns:
            The generated response as a string
        """
        messages = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        messages.append(HumanMessage(content=prompt))
        
        response = self.model.invoke(messages)
        return response.content
    
    def chat(self, messages: list) -> str:
        """
        Generate a response from a conversation history
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     roles: 'system', 'user', 'assistant'
                     
        Returns:
            The generated response as a string
        """
        langchain_messages = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role in ["user", "human"]:
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(HumanMessage(content=content))
        
        response = self.model.invoke(langchain_messages)
        return response.content


# Singleton instance
_gemini_service = None


def get_gemini_service() -> GeminiService:
    """Get or create the Gemini service singleton"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
