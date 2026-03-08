import os
import re
import ollama

class SLDSpecMaster:
    def __init__(self, c_file_path, model_name="llama3"):
        self.c_file_path = c_file_path
        self.model_name = model_name
        self.output_dir = "verification"
        os.makedirs(self.output_dir, exist_ok=True)
        
        with open(c_file_path, 'r') as f:
            self.source_code = f.read()

    def get_slices(self):
        var_pattern = r'\bint\s*\*?\s*([a-zA-Z_]\w*)'
        variables = list(set(re.findall(var_pattern, self.source_code)))
        slices = {}
        lines = self.source_code.split('\n')
        for var in variables:
            relevant_lines = [l for l in lines if var in l]
            slices[var] = "\n".join(relevant_lines)
        return slices

    def process_slices(self, slices):
        verified_specs = []

        for var, code_slice in slices.items():
            print(f"\n" + "="*50)
            print(f"STAGING AREA: Variable '{var}'")
            print("="*50)
            
            # PHASE 2: GUESSING
            guess_prompt = f"Task: Write one ACSL 'ensures' line for variable '{var}' in this code:\n{code_slice}\nReturn ONLY the code."
            guess_res = ollama.chat(model=self.model_name, messages=[{'role': 'user', 'content': guess_prompt}])
            candidate_spec = guess_res['message']['content'].strip()
            print(f"AI PROPOSED SPEC: {candidate_spec}")
            
            # PHASE 3: LOGICAL DELETION WITH REASONING
            # We ask the AI to explain ITS reasoning before giving the verdict
            judge_prompt = f"""
            Code: {code_slice}
            Spec: {candidate_spec}
            
            Analyze the Spec above:
            1. Does the math in the Spec match the math in the Code?
            2. Does the Spec use variables that are NOT in the Code?
            
            Provide a 1-sentence explanation, then end with 'VERDICT: KEEP' or 'VERDICT: DELETE'.
            """
            judge_res = ollama.chat(model=self.model_name, messages=[{'role': 'user', 'content': judge_prompt}])
            reasoning = judge_res['message']['content'].strip()
            
            print(f"\nJUDGE'S REASONING:\n{reasoning}")

            if "VERDICT: KEEP" in reasoning.upper():
                print(f"\nFINAL DECISION: [KEEP] - Added to verification set.")
                clean_spec = re.sub(r'```.*?```', '', candidate_spec, flags=re.DOTALL).strip()
                verified_specs.append(clean_spec)
            else:
                print(f"\nFINAL DECISION: [DELETE] - Spec was discarded.")
        
        return verified_specs

    def run(self):
        slices = self.get_slices()
        kept_specs = self.process_slices(slices)
        
        if kept_specs:
            # Consolidation
            acsl_block = "/*@\n  " + "\n  ".join(list(set(kept_specs))) + "\n*/"
            final_code = acsl_block + "\n" + self.source_code
            with open(os.path.join(self.output_dir, "final_verified_program.c"), "w") as f:
                f.write(final_code)
            print(f"\nPipeline finished. Check the 'verification' folder.")
        else:
            print("\nPipeline finished. No specs passed the logic test.")

if __name__ == "__main__":
    pipeline = SLDSpecMaster("slicing/test_program.c")
    pipeline.run()