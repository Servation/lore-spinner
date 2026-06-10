import re
import inspect
from typing import Dict, Callable

# ANSI Styling for Agents
COLOR_THOUGHT = "\033[90m"   # Dark grey for background agents
COLOR_ACTION = "\033[90m"
COLOR_OBSERVE = "\033[90m"
COLOR_ANSWER = "\033[90m"
COLOR_RESET = "\033[0m"

class BaseAgent:
    """Base class for ReAct-style agents."""
    
    def __init__(self, llm_client, tools: Dict[str, Callable], system_instruction: str = ""):
        self.llm_client = llm_client
        self.tools = tools
        self.system_instruction = system_instruction

    def run(self, query: str, max_turns: int = 5, verbose: bool = False, agent_name: str = "Agent") -> str:
        """Executes the ReAct loop (Thought, Action, Observe, Answer) for a single query."""
        prompt = f"Question: {query}\n"
        if verbose:
            print(f"\n{COLOR_THOUGHT}[{agent_name}] Processing query: {query}{COLOR_RESET}")
            
        for turn in range(max_turns):
            if verbose:
                print(f"{COLOR_THOUGHT}[{agent_name}] --- Turn {turn + 1} ---{COLOR_RESET}")
                
            # 1. Generate response from LLM
            response = self.llm_client.generate(prompt, system_instruction=self.system_instruction)
            
            # Truncate response if it contains an Action: line to prevent the model from simulating/hallucinating observations or subsequent turns.
            lines = response.splitlines()
            truncated_lines = []
            action_found = False
            for line in lines:
                truncated_lines.append(line)
                if line.strip().startswith("Action:"):
                    action_found = True
                    break
            if action_found:
                response = "\n".join(truncated_lines)
            
            if verbose:
                # Print styled lines for thoughts/actions
                for line in response.splitlines():
                    print(f"{COLOR_THOUGHT}[{agent_name}] {line}{COLOR_RESET}")
                    
            prompt += f"{response}\n"
            
            # 2. Check for action
            action_line = None
            for line in response.splitlines():
                if line.strip().startswith("Action:"):
                    action_line = line.strip()
                    break
                    
            if action_line:
                # Parse: Action: tool_name: tool_arguments
                try:
                    raw_action = action_line.split("Action:", 1)[1].strip()
                    if ":" in raw_action:
                        tool_name, tool_arg = raw_action.split(":", 1)
                        tool_name = tool_name.strip()
                        tool_arg = tool_arg.strip()
                    else:
                        tool_name = raw_action
                        tool_arg = ""
                except Exception:
                    tool_name, tool_arg = None, None
                    
                if tool_name:
                    if tool_name in self.tools:
                        if verbose:
                            print(f"{COLOR_THOUGHT}[{agent_name}] Executing '{tool_name}' with: '{tool_arg}'{COLOR_RESET}")
                        try:
                            # Inject dependency (like llm_client) dynamically if requested
                            sig = inspect.signature(self.tools[tool_name])
                            kwargs = {}
                            if "llm_client" in sig.parameters:
                                kwargs["llm_client"] = self.llm_client
                                
                            observation = self.tools[tool_name](tool_arg, **kwargs)
                        except Exception as e:
                            observation = f"Error executing tool: {e}"
                    else:
                        observation = f"Error: Tool '{tool_name}' is not registered."
                        
                    obs_line = f"Observation: {observation}"
                    if verbose:
                        print(f"{COLOR_THOUGHT}[{agent_name}] {obs_line}{COLOR_RESET}")
                    prompt += f"{obs_line}\n"
                else:
                    error_line = "Observation: Error: Invalid Action syntax. Expected 'Action: tool_name: argument'"
                    if verbose:
                        print(f"{COLOR_THOUGHT}[{agent_name}] {error_line}{COLOR_RESET}")
                    prompt += f"{error_line}\n"
                continue
                
            # 3. Check for answer
            answer_match = re.search(r"Answer:\s*(.*)", response, re.DOTALL)
            if answer_match:
                return answer_match.group(1).strip()
                
            # Safeguard if no action or answer
            if response.strip() and "Action:" not in response:
                return response.strip()
                
        return f"[{agent_name}] Failed to arrive at an answer within turn limit."
