import os
import re
from dotenv import load_dotenv
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.messages import SystemMessage, HumanMessage

# Load env variables
load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Meta-Llama-3-8B-Instruct")
API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")

if not API_TOKEN:
    print("Error: HUGGINGFACEHUB_API_TOKEN not found in environment.")
    exit(1)

SYSTEM_PROMPT = """
You are an expert coding agent. Write production-quality code.
Output your files using EXACTLY this format for EVERY file:
### FILE: <filename>
```<language>
<complete source code>
```
Provide the full runnable code. After all file blocks, you may provide a brief explanation.
"""

def parse_and_write_files(response_text: str):
    pattern = r"### FILE:\s*([^\n]+)\n```[^\n]*\n(.*?)```"
    matches = re.finditer(pattern, response_text, re.DOTALL)
    
    files_written = 0
    for match in matches:
        filename = match.group(1).strip()
        code = match.group(2)
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)
            
        print(f"📄 Created/Updated: {filename}")
        files_written += 1
        
    if files_written == 0:
        print("No files were parsed. LLM response:")
        print(response_text)

def main():
    print(f"🤖 Starting Code Agent (Model: {MODEL_NAME})")
    print("Type 'exit' or 'quit' to stop.\n")
    
    # Initialize the LLM via HF Inference Endpoint
    llm = HuggingFaceEndpoint(
        repo_id=MODEL_NAME,
        task="text-generation",
        max_new_tokens=4096,
        temperature=0.1,
    )
    chat_model = ChatHuggingFace(llm=llm)

    while True:
        try:
            task = input("\n📝 Enter your task: ")
            if task.lower() in ["exit", "quit"]:
                break
            if not task.strip():
                continue
                
            print("⏳ Thinking...")
            
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=task)
            ]
            
            # Call the LLM
            response = chat_model.invoke(messages)
            
            print("\n" + "="*50)
            parse_and_write_files(response.content)
            print("="*50)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
