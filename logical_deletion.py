import os
import ollama

class LogicalDeleter:
    def __init__(self, model_name="llama3"):
        self.model_name = model_name
        self.input_folder = "guessing"
        self.output_folder = "logical_deletion"

    def verify_logic(self, var_name, content):
        """Phase 3: LLM-as-a-Judge reasoning."""
        prompt = f"""
        You are a Logic Judge. You are evaluating an ACSL specification for the variable '{var_name}'.
        
        {content}
        
        Step 1: Does this specification accurately describe what the code is doing?
        Step 2: Are there any variables in the spec that don't exist in the slice?
        
        Reason step-by-step. At the end, output ONLY 'STATUS: KEEP' or 'STATUS: DELETE'.
        """
        
        response = ollama.chat(
            model=self.model_name,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']

    def run(self):
        for filename in os.listdir(self.input_folder):
            if filename.endswith("_spec.txt"):
                var_name = filename.replace("_spec.txt", "")
                with open(os.path.join(self.input_folder, filename), "r") as f:
                    content = f.read()
                
                print(f"Judging logic for {var_name}...")
                judgment = self.verify_logic(var_name, content)
                
                # Save the 'Cleaned' version
                output_path = os.path.join(self.output_folder, f"{var_name}_verified.txt")
                with open(output_path, "w") as f:
                    f.write(judgment)
                print(f"Result: {judgment.splitlines()[-1]}")

if __name__ == "__main__":
    deleter = LogicalDeleter()
    deleter.run()