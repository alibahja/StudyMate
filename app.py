from pathlib import Path
import traceback
import uvicorn
from fastapi import FastAPI,Request, UploadFile,File, HTTPException, Form, Cookie, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from backend import run_study_agent
import base64
import uuid
import os
from datetime import datetime, timedelta
from fpdf import FPDF
from mcp_client import extract_pdf, extract_docx, get_document_stats
import psycopg
from psycopg.rows import dict_row
import hashlib
import secrets
from dotenv import load_dotenv

load_dotenv()

import nest_asyncio
nest_asyncio.apply()

BASE_DIR=Path(__file__).resolve().parent

DOWNLOADS_DIR=BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# ==========================================
# Database Connection
# ==========================================

def get_db_connection():
    """Get PostgreSQL connection."""
    database_url=os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing. Please add it to .env")
    return psycopg.connect(database_url,autocommit=True,row_factory=dict_row)


# ==========================================
# Password Hashing
# ==========================================

def hash_password(password: str)->str:
      """Hash a password using SHA-256 with salt."""
      salt=secrets.token_hex(16)
      hash_obj=hashlib.sha256((salt+password).encode())
      return f"{salt}:{hash_obj.hexdigest()}"

def verify_password(password: str, hashed:str)->bool:
     """Verify a password against its hash."""
     salt,hash_value=hashed.split(":")
     hash_obj=hashlib.sha256((salt+password).encode())
     return hash_obj.hexdigest() == hash_value

# ==========================================
# FastAPI APP
# ==========================================

app = FastAPI(
    title="Autonomous Study Companion",
    description="Multi-Agent LLM System for Lecture Analysis and Study Material Generation",
    version="1.0.0"
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

templates=Jinja2Templates(
    directory=(BASE_DIR / "templates")
)

#====================
#Pydantic Models
#====================

class StudyRequest(BaseModel):
    thread_id: str | None=None
    user_query: str | None=""

class PDFDownloadRequest(BaseModel):
    thread_id: str
    content: dict

class LoginRequest(BaseModel):
    username: str
    password:str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

# ==========================================
# Authentication Dependencies
# ==========================================
def get_current_user(session_token: str= Cookie(None)):
    """Get current user from session cookie."""
    if not session_token:
        return None

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM sessions WHERE session_token = %s AND expires_at > NOW()",
                (session_token,)
            )
            result=cur.fetchone()
            if result:
                return result["user_id"]
    return None

#========================
#Helper: Generate PDF
#========================
def generate_study_pdf(content: dict, thread_id: str) -> str:
    """Generate a PDF from the study content."""
    
    pdf = FPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Autonomous Study Companion - Study Materials", ln=True, align="C")
    pdf.ln(10)
    
    # Thread ID and Date
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 5, f"Thread ID: {thread_id}", ln=True)
    pdf.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(10)
    
    # Explanation
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "1. Explanation", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, content.get("explanation", "N/A"))
    pdf.ln(5)
    
    # Summary
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "2. Summary", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, content.get("summary", "N/A"))
    pdf.ln(5)
    
    # MCQs
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "3. Multiple Choice Questions", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, content.get("mcqs", "N/A"))
    pdf.ln(5)
    
    # Subjective Questions
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "4. Subjective Questions", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, content.get("subjective_questions", "N/A"))
    pdf.ln(5)
    
    # Solutions
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "5. Solutions", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, content.get("solutions", "N/A"))
    pdf.ln(5)
    
    # Footer
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 10, f"Generated by Autonomous Study Companion - {datetime.now().year}", ln=True, align="C")
    
    # Save PDF
    pdf_path = DOWNLOADS_DIR / f"study_materials_{thread_id}.pdf"
    pdf.output(str(pdf_path))
    
    return str(pdf_path)

#Routes
@app.get("/",response_class=HTMLResponse)
async def home(request:Request,user_id: int=Depends(get_current_user)):
    """ Serve the main page. """
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user_id":user_id, "is_authenticated": user_id is not None}
    )


@app.get("/login",response_class=HTMLResponse)
async def login_page(request:Request):
    """ Serves the login page. """
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )

@app.get("/register",response_class=HTMLResponse)
async def register_page(request: Request):
    """ Serves the register page. """
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={}
    )

@app.post("/api/register")
async def register_user(register_data:RegisterRequest):
    """ Register a new user. """
    try:
        #Check if username exits
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                     "SELECT id FROM users WHERE username = %s OR email = %s",
                     (register_data.username, register_data.email)
                )
                if cur.fetchone():
                    return JSONResponse(
                        status_code=400,
                        content={"success":False,"error":"Username or email already exists."}
                    )
        #Hash passowrd and insert user
        hashed=hash_password(register_data.password)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (register_data.username,register_data.email,hashed)
                )
                user_id=cur.fetchone()["id"]
        return JSONResponse(
            content={"success":True,"message": "User registered successfully"}
        )
    except Exception as e:
        print("❌ Registration error:", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/login")
async def login_user(login_data: LoginRequest):
    """Login user."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, username, password_hash FROM users WHERE username = %s",
                    (login_data.username,)  # ✅ Fixed: comma after username
                )
                user = cur.fetchone()
                
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Invalid username or password."}
            )
            
        if not verify_password(login_data.password, user["password_hash"]):  # ✅ Fixed: password_hash
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Invalid username or password."}
            )

        # Create session token
        session_token = secrets.token_hex(32)
        expires_at = datetime.now() + timedelta(days=7)

        # Save session
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (user_id, session_token, expires_at) VALUES (%s, %s, %s)",
                    (user["id"], session_token, expires_at)
                )

        # Set cookie
        response = JSONResponse(
            content={"success": True, "message": "Login successful", "redirect": "/"}
        )
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=604800,
            path="/"
        )
        return response
        
    except Exception as e:
        print("❌ Login error:", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/logout")
async def logout_user():
    """ Logout a user. """
    response=RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response
        
@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, user_id: int = Depends(get_current_user)):
    """Serve the history page with user's study sessions."""
    if not user_id:
        return RedirectResponse(url="/login")
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT thread_id, document_name, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at FROM study_sessions WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            sessions = cur.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"sessions": sessions, "user_id": user_id}
    )

@app.post("/api/upload")
async def upload_lecture(
    request: Request,
    file: UploadFile= File(...),
    thread_id: str | None=None,
    user_query: str="",
    user_id:int=Depends(get_current_user)
):
    """
    Upload a lecture (PDF or Word) and generate study materials.
    Requires authentication.
    """

    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        #Validate file type
        allowed_extensions=[".pdf",".docx"]
        file_extension=Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )

        #Generate thread Id if not provided
        if not thread_id:
            thread_id=f"study_{uuid.uuid4().hex}"

        #Read file content
        file_content=await file.read()

        #Encode to base64 for MCP transport
        file_base64=base64.b64encode(file_content).decode('utf-8')

        #Extract text based on file type
        if file_extension ==".pdf":
            document_text=await extract_pdf(file_base64)
        else:
            document_text=await extract_docx(file_base64)

        #check if the document extraction was successful 
        if not document_text or len(document_text.strip())<10:
            raise HTTPException(
                status_code=400,
                detail="Failed to extract text from the document. Please ensure it contains readable text."
            )

        #Get Document Stats
        stats=await get_document_stats(document_text)

        print(f"\n📄 Document Stats:")
        print(f"  - Word count: {stats.get('word_count', 0)}")
        print(f"  - Character count: {stats.get('character_count', 0)}")
        print(f"  - Estimated pages: {stats.get('estimated_pages', 0):.1f}")
        print(f"  - Thread ID: {thread_id}")
        print(f"  - User ID: {user_id}")

        # Save session to database
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO study_sessions (user_id, thread_id, document_name) VALUES (%s, %s, %s)",
                    (user_id, thread_id, file.filename)
                )

        #run the study agent
        print("\n🤖 Running study agent pipeline...")
        result=run_study_agent(
            document_text=document_text,
            user_query=user_query,
            thread_id=thread_id
        )

        print(f"✅ Study materials generated! (LLM calls: {result.get('llm_calls', 0)})")

        #Generate PDF
        pdf_path=generate_study_pdf(result,thread_id)

        return JSONResponse(
            content={
                "success": True,
                "thread_id": thread_id,
                "explanation": result.get("explanation", ""),
                "summary": result.get("summary", ""),
                "mcqs": result.get("mcqs", ""),
                "subjective_questions": result.get("subjective_questions", ""),
                "solutions": result.get("solutions", ""),
                "llm_calls": result.get("llm_calls", 0),
                "word_count": stats.get("word_count", 0),
                "download_url": f"/api/download/{thread_id}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.get("/api/download/{thread_id}")
async def download_pdf(thread_id: str, user_id: int = Depends(get_current_user)):
    """Download the generated PDF. Requires authentication."""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    pdf_path = DOWNLOADS_DIR / f"study_materials_{thread_id}.pdf"
    
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    
    return FileResponse(
        path=pdf_path,
        filename=f"study_materials_{thread_id}.pdf",
        media_type="application/pdf"
    )

@app.get("/api/history/{thread_id}")
async def get_history(thread_id: str, user_id: int = Depends(get_current_user)):
    """Retrieve study materials for a specific thread. Requires authentication."""
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Authentication required"}
        )
    
    pdf_path = DOWNLOADS_DIR / f"study_materials_{thread_id}.pdf"
    
    if pdf_path.exists():
        return JSONResponse(
            content={
                "exists": True,
                "thread_id": thread_id,
                "download_url": f"/api/download/{thread_id}"
            }
        )
    else:
        return JSONResponse(
            content={
                "exists": False,
                "thread_id": thread_id,
                "message": "No study materials found for this thread ID."
            }
        )

@app.get("/api/check-auth")
async def check_auth(user_id: int = Depends(get_current_user)):
    """Check if user is authenticated."""
    if user_id:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                return {"authenticated": True, "username": user["username"]}
    return {"authenticated": False}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Autonomous Study Companion API is running"
    }


@app.get("/api/user-history")
async def get_user_history(user_id: int = Depends(get_current_user)):
    """Get all study sessions for the current user."""
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Authentication required"}
        )
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT thread_id, document_name, created_at FROM study_sessions WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            sessions = cur.fetchall()
    
    # Convert datetime to string
    for session in sessions:
        if isinstance(session["created_at"], datetime):
            session["created_at"] = session["created_at"].isoformat()
    
    return JSONResponse(
        content={
            "success": True,
            "sessions": sessions
        }
    )

@app.get("/favicon.ico")
async def favicon():
    """Favicon placeholder."""
    return JSONResponse(content={})

if __name__=="__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )