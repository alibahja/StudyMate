import os
import certifi
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"]=certifi.where()
os.environ["REQUESTS_CA_BUNDLE"]=certifi.where()

from typing import TypedDict, Annotated
import operator
import uuid
import psycopg
from psycopg.rows import dict_row

from langgraph.graph import START, StateGraph,END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage
)
from mcp_client import get_llm

#Database setup

def get_database_url():
    databse_url=os.getenv("DATABASE_URL")

    if not databse_url:
        raise ValueError(
            "DATABASE_URL is missing. Please add your PostgreSQL Database URL to .env"
        )
    if "sslmode=" not in databse_url:
        separator="&" if "?" in databse_url else "?"
        databse_url=f"{databse_url}{separator}sslmode=require"

    return databse_url

#State Definition
class StudyState(TypedDict):
    messages:Annotated[list[AnyMessage],operator.add]
    user_query: str
    document_text: str
    explanation: str
    summary: str
    mcqs: str
    subjective_questions: str
    solutions: str
    llm_calls: str

# Agent 1: Explanation Agent
EXPLANATION_PROMPT = """
You are an expert educator. Your task is to explain the following lecture content 
in a clear, comprehensive, and easy-to-understand way.

Lecture Content:
{document_text}

Instructions:
1. Break down complex concepts into simple terms
2. Use examples where helpful
3. Organize the explanation logically
4. Highlight key definitions and important concepts
5. Keep it thorough but not overly verbose

Return a well-structured explanation.
"""
def explanation_agent(state: StudyState):
     print("\n🤖 EXPLANATION AGENT: Generating explanation...\n")
     prompt=EXPLANATION_PROMPT.format(
         document_text=state["document_text"][:10000] #limit to avoid token overflow
     )

     llm=get_llm()

     response=llm.invoke([
         SystemMessage(content="You are an expert educator"),
         HumanMessage(content=prompt)
     ])
     return {
         "explanation":response.content,
         "messages":[AIMessage(content="Explanation generated.")],
         "llm_calls":state.get("llm_calls",0)+1
       }

# Agent 2: Summary Agent 
SUMMARY_PROMPT = """
You are an expert summarizer. Create a concise summary of the following lecture.

Lecture Content:
{document_text}

Instructions:
1. Identify the 5-7 most important points
2. Keep it brief (max 300 words)
3. Use bullet points for easy reading
4. Focus on key takeaways
5. Include any critical definitions

Return a clear, bulleted summary.
"""

def summary_agent(state: StudyState):
     print("\n🤖 SUMMARY AGENT: Generating summary...\n")

     prompt=SUMMARY_PROMPT.format(
         document_text=state["document_text"][:10000]
     )
     llm=get_llm()
     response=llm.invoke([
         SystemMessage(content="You are an expert summarizer"),
         HumanMessage(content=prompt)
     ]
     )
     return {
         "summary":response.content,
         "messages":[AIMessage(content="Summary generated")],
         "llm_calls":state.get("llm_calls",0)+1
     }

#Agent 3: MCQ Generator
MCQ_PROMPT = """
You are an expert test creator. Generate 5 multiple-choice questions based on the lecture.

Lecture Content:
{document_text}

Instructions:
1. Create 5 MCQs with 4 options each (A, B, C, D)
2. Each question should test understanding, not just memorization
3. Make the distractors (wrong answers) plausible
4. Include the correct answer at the end of each question
5. Cover different sections of the lecture

Format each question as:

Q1: [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
**Answer: [Correct option letter]**

Return exactly 5 questions in this format.
"""
def mcq_agent(state: StudyState):
    print("\n🤖 MCQ AGENT: Generating multiple-choice questions...\n")

    prompt=MCQ_PROMPT.format(
        document_text=state["document_text"][:10000]
    )
    llm=get_llm()
    response=llm.invoke([
        SystemMessage(content="You are an expert text creator."),
        HumanMessage(content=prompt)
    ]
    )
    return {
        "mcqs":response.content,
        "messages":[AIMessage(content="MCQs generated.")],
        "llm_calls":state.get("llm_calls",0)+1
    }

# Agent 4: Subjective Questions Generator
SUBJECTIVE_PROMPT = """
You are an expert educator. Generate 5 subjective (open-ended) questions based on the lecture.

Lecture Content:
{document_text}

Instructions:
1. Questions should require critical thinking
2. Cover major concepts from the lecture
3. Questions should be answerable in 3-5 sentences each
4. Make questions that demonstrate understanding

Return exactly 5 subjective questions numbered Q1, Q2, Q3, Q4, Q5.
"""

def subjective_agent(state: StudyState):
    print("\n🤖 SUBJECTIVE AGENT: Generating subjective questions...\n")

    prompt=SUBJECTIVE_PROMPT.format(
        document_text=state["document_text"][:10000]
    )
    llm=get_llm()
    response = llm.invoke([
        SystemMessage(content="You are an expert educator."),
        HumanMessage(content=prompt)
    ])
    return {
        "subjective_questions":response.content,
        "messages":[AIMessage(content="Subjective questions generated.")],
        "llm_calls":state.get("llm_calls",0)+1
    }


# Agent 5: Solution Generator
SOLUTIONS_PROMPT = """
You are an expert educator. Provide detailed solutions to ALL the questions (MCQs and subjective) 
that were created based on this lecture.

Lecture Content:
{document_text}

MCQs:
{mcqs}

Subjective Questions:
{subjective_questions}

Instructions:
1. For MCQs: Explain WHY each correct answer is correct
2. For MCQs: Explain briefly why each distractor is wrong
3. For Subjective: Provide comprehensive model answers (3-5 sentences each)
4. Be thorough and educational

Structure your response as:

## MCQ Solutions
[Solutions for each MCQ]

## Subjective Solutions
[Solutions for each subjective question]
"""

def solutions_agent(state: StudyState):
    print("\n🤖 SOLUTIONS AGENT: Generating solutions...\n")

    prompt=SOLUTIONS_PROMPT.format(
        document_text=state["document_text"][:10000],
        mcqs=state["mcqs"],
        subjective_questions=state["subjective_questions"]
    )
    llm=get_llm()
    response=llm.invoke([
         SystemMessage(content="You are an expert educator."),
         HumanMessage(content=prompt)
    ]
    )
    return {
        "solutions":response.content,
        "messages": [AIMessage(content="Solutions generated.")],
        "llm_calls":state.get("llm_calls",0)+1
    }

#build the graph (Pipeline)

graph=StateGraph(StudyState)

# Add all nodes
graph.add_node("explanation_agent", explanation_agent)
graph.add_node("summary_agent", summary_agent)
graph.add_node("mcq_agent", mcq_agent)
graph.add_node("subjective_agent", subjective_agent)
graph.add_node("solutions_agent", solutions_agent)

# Define the pipeline order (linear)
graph.add_edge(START, "explanation_agent")
graph.add_edge("explanation_agent", "summary_agent")
graph.add_edge("summary_agent", "mcq_agent")
graph.add_edge("mcq_agent", "subjective_agent")
graph.add_edge("subjective_agent", "solutions_agent")
graph.add_edge("solutions_agent", END)

#PostGreSQL Checkpointer

DATABASE_URL=get_database_url()

_conn=psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)
checkpointer=PostgresSaver(_conn)
checkpointer.setup()

study_graph=graph.compile(checkpointer=checkpointer)

#Main Function: called by app.py

def run_study_agent(
    document_text: str,
    user_query: str = "",
    thread_id: str | None = None
):
    """
    Main entry point for the study companion agent.
    
    Args:
        document_text: Extracted text from the uploaded document
        user_query: Optional user instructions
        thread_id: Optional conversation thread ID for memory
    
    Returns:
        Dictionary with all generated content
    """
    if not thread_id:
        thread_id= f"study_{uuid.uuid4().hex}"

    config={
        "configurable": {
            "thread_id":thread_id
        }
    }

    # Initial state
    initial_state = {
        "messages": [HumanMessage(content="Generate study materials from this lecture.")],
        "user_query": user_query,
        "document_text": document_text,
        "explanation": "",
        "summary": "",
        "mcqs": "",
        "subjective_questions": "",
        "solutions": "",
        "llm_calls": 0
    }

    # run the graph
    result=study_graph.invoke(initial_state,config=config)

    #Extract final results
    return {
        "thread_id": thread_id,
        "explanation": result.get("explanation", ""),
        "summary": result.get("summary", ""),
        "mcqs": result.get("mcqs", ""),
        "subjective_questions": result.get("subjective_questions", ""),
        "solutions": result.get("solutions", ""),
        "llm_calls": result.get("llm_calls", 0),
    }