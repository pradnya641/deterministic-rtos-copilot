import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import argparse

def extract_text_langchain(pdf_path: str):
    """
    Extracts text from a PDF using Langchain's PyPDFLoader.
    """
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    text = "\n".join([doc.page_content for doc in documents])
    return text

def process_pdf(pdf_path: str, board: str):
    """
    Ingests a PDF, splits it into chunks, creates embeddings, and saves to a FAISS index.
    """
    print(f"Processing {pdf_path} for board {board}...")
    
    # Ensure the db directory exists
    db_dir = f"../app/db/{board}_index"
    os.makedirs(db_dir, exist_ok=True)
    
    # 1. Extract text
    text = extract_text_langchain(pdf_path)
    print(f"Extracted {len(text)} characters.")
    
    # 2. Split text into chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_text(text)
    print(f"Created {len(chunks)} chunks.")
    
    # 3. Create Embeddings
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print("Encoding chunks...")
    embeddings = model.encode(chunks)
    
    # 4. Create and Save FAISS index
    # 'all-MiniLM-L6-v2' has embedding dimension 384
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    
    index_path = os.path.join(db_dir, "index.faiss")
    faiss.write_index(index, index_path)
    
    # 5. Save the chunks to map back from indices later
    chunks_path = os.path.join(db_dir, "chunks.txt")
    with open(chunks_path, 'w', encoding='utf-8') as f:
        # Using a custom separator that is unlikely to appear in the text
        f.write("\n---CHUNK_SEP---\n".join(chunks))
        
    print(f"Successfully saved FAISS index and chunks to {db_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF manual for a specific board.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF manual")
    parser.add_argument("board", type=str, help="Name of the board (e.g., lpc2148, rpi)")
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_path):
        print(f"Error: File '{args.pdf_path}' not found.")
        exit(1)
        
    process_pdf(args.pdf_path, args.board)
