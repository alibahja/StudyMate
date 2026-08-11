import os
import certifi
import sys
from dotenv import load_dotenv
from pathlib import Path
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient

#Environment configuration

os.environ["SSL_CERT_FILE"]=certifi.where()
os.environ["REQUESTS_CA_BUNDLE"]=certifi.where()

load_dotenv()

GROQ_API_KEY=os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")

#automatically find the current project folder

PROJECT_DIR=Path(__file__).resolve().parent
PARSER_SERVER_PATH=PROJECT_DIR/"custom_document_parser_mcp.py"

#==========================================
#Model Router - Quota-aware + Failover
#==========================================

GROQ_MODELS=[
    "llama-3.3-70b-versatile",  # Best quality (your current one)
    "qwen/qwen3.6-27b",         # High quality, good alternative
    "llama-3.1-8b-instant", 
]

#track usage per model (reset when app restarts)
_model_usage={model: 0 for model in GROQ_MODELS}
#groq free tier limits (requests per day)
_MODEL_QUOTAS={
    "llama-3.3-70b-versatile": 10000,
    "qwen/qwen3.6-27b": 10000,
    "llama-3.1-8b-instant": 10000
}

def get_availabe_groq_models():
    """
    Returns the first Groq model with remaining quota.
    If all are exhausted, raises an exception.
    """
    for model in GROQ_MODELS:
         if _model_usage[model] < _MODEL_QUOTAS[model]:
             return model
    #All models exhausted
    raise Exception(
        "All Groq models have reached their daily quota. "
        "Please try again tomorrow or use a different API."
    )

def increment_model_usage(model_name: str):
     """Increment usage counter for a model."""
     if model_name in _model_usage:
         _model_usage[model_name]+=1

def get_llm():
    """
    Creates a ChatGroq instance with an available model.
    Implements quota-aware selection with failover.
    """
    model_name=get_availabe_groq_models()
    increment_model_usage(model_name)

    print(f"🔀 Using Groq model: {model_name} (usage: {_model_usage[model_name]}/{_MODEL_QUOTAS[model_name]})")

    return ChatGroq(
        model=model_name,
        api_key=GROQ_API_KEY
    )

#=====================================
# LLMs (for backward compatibility)
#=====================================

groq_model=ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY
)


# MCP client configuration
client=MultiServerMCPClient(
    {
        "document_parser":{
            "transport":"stdio",
            "command":sys.executable,
            "args":[str(PARSER_SERVER_PATH)],
        }
    }
)

#Document parser tools
extract_pdf_tool=None
extract_docx_tool=None
stats_tool=None

async def initialize_parser_tools():
    """ Initialize all documents parser tools. """
    global extract_pdf_tool, extract_docx_tool, stats_tool

    if extract_pdf_tool is not None:
        return #already initialized

    tools=await client.get_tools(server_name="document_parser")
    tools_by_name={tool.name: tool for tool in tools}

    extract_pdf_tool=tools_by_name.get("extract_text_from_pdf")
    extract_docx_tool=tools_by_name.get("extract_text_from_docx")
    stats_tool=tools_by_name.get("return_document_stats")

    missing_tools=[]
    if extract_pdf_tool is None:
        missing_tools.append("extract_text_from_pdf")
    if extract_docx_tool is None:
        missing_tools.append("extract_text_from_docx")
    if stats_tool is None:
        missing_tools.append("return_document_stats")

    if missing_tools:
        available_tools=", ".join(tools_by_name.keys())
        raise RuntimeError(
             f"Missing document parser tools: {', '.join(missing_tools)}. "
             f"Available tools: {available_tools or 'none'}"
        )

async def extract_pdf(pdf_base64: str) -> str:
    """Extract text from a PDF file."""
    await initialize_parser_tools()
    result = await extract_pdf_tool.ainvoke({"pdf_base64": pdf_base64})
    
    # ✅ FIX: Handle if result is a list or dict
    if isinstance(result, list):
        return " ".join(str(item) for item in result)
    elif isinstance(result, dict):
        return result.get("text", str(result))
    else:
        return str(result)

async def extract_docx(docx_base64: str) -> str:
    """Extract text from a DOCX file."""
    await initialize_parser_tools()
    result = await extract_docx_tool.ainvoke({"docx_base64": docx_base64})
    
    # ✅ FIX: Handle if result is a list or dict
    if isinstance(result, list):
        return " ".join(str(item) for item in result)
    elif isinstance(result, dict):
        return result.get("text", str(result))
    else:
        return str(result)

async def get_document_stats(text: str) -> dict:
    """Get statistics about the document."""
    await initialize_parser_tools()
    result = await stats_tool.ainvoke({"text": text})
    
    # ✅ FIX: Handle if result is a list
    if isinstance(result, list) and len(result) > 0:
        return result[0] if isinstance(result[0], dict) else {"raw": result}
    elif isinstance(result, dict):
        return result
    else:
        return {"raw": result}

#========================
#Diagnostic function
#========================

async def get_all_tools():
    """ Debug function to print all available tools. """
    try:
        tools= await client.get_tools(server_name="document_parser")
        print("\nAvailable tools from Document Parser MCP:\n")
        for tool in tools:
            print(f"  -{tool.name}")
        return tools
    except Exception as error: 
        print(f"\nCould not connect to Document Parser MCP:\n{error}\n")
        return []
        