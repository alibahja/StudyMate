from mcp.server.fastmcp import FastMCP
import PyPDF2
import docx
import io
import base64

mcp=FastMCP("Document Parser MCP Server")


@mcp.tool()
def extract_text_from_pdf(pdf_base64:str)->str:
    """ 
      Extracts text from a PDF file.
      Input: Base64-encoded PDF content
      Output: Extracted text as string
    """

    #Decode base64
    pdf_bytes=base64.b64decode(pdf_base64)

    #create a pdf reader
    pdf_reader=PyPDF2.PdfReader(io.BytesIO(pdf_bytes))

    #extract text from all pages
    text=""
    for page in pdf_reader.pages:
        text+=page.extract_text()+"\n"
    return text

@mcp.tool()
def extract_text_from_docx(docx_base64:str)->str:
    """ 
      Extracts text from a Word document
      Input: Base64-encoded DOCX content
      Output: Extracted text as string 
    """

    #Decode base64
    docx_bytes=base64.b64decode(docx_base64)

    #read DOCX
    doc=docx.Document(io.BytesIO(docx_bytes))

    #extract text from paragraphs
    text=""
    for para in doc.paragraphs:
        text+=para.text+"\n"
    return text

@mcp.tool()
def return_document_stats(text:str)->dict:
    """  
      Return statistics about the document (word count, etc.)
    """
    words=text.split()
    return {
         "word_count":len(words),
         "character_count":len(text),
         "estimated_pages":len(text)/3000  #Rough estimate
    }

if __name__=="__main__":
    mcp.run()