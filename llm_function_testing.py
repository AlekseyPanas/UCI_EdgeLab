import ollama
from abc import abstractmethod


class LLMInterface:
    @abstractmethod
    def convert(self, constraint_prompt: str, model: str) -> list[tuple[str, int]]:
        """"""

    @abstractmethod
    def verify(self, predicate: str, val: str, model: str) -> bool:
        """"""


class OllamaLLM(LLMInterface):
    PROMPT_FOLDER_PATH = "./prompts"
    CONVERT_FILENAME = "CONVERT_V1"
    VERIFY_FILENAME = "VERIFY_V1"

    def __init__(self):
        self.__convert_prompt = ""
        with open(OllamaLLM.PROMPT_FOLDER_PATH + OllamaLLM.CONVERT_FILENAME, "r") as file:
            file.readline()

    def convert(self, constraint_prompt: str, model: str) -> list[tuple[str, int]]:
        pass

    def verify(self, predicate: str, val: str, model: str) -> bool:
        pass


def convert(constraint_prompt: str, model: str) -> list[tuple[str, int]]:
    convert_prompt = "You are a service being used as part of a distributed software application. " \
                     "This service is run on every process in the network. You are responsible for processing " \
                     "a given input to a defined function and providing an output according to the function descriptions. " \
                     "For this reason, your reply must be exactly according to the output spec described. " \
                     "The application is a distributed constrained consensus solver. Users would like to coordinate " \
                     "with each other to agree on a value. Each user provides their constraints to their agent/process " \
                     "on what the value can be. These agents then communicate and arrive at consensus on a value that " \
                     "satisfies constraints. Some constraints can be specified as \"relaxable\", meaning they are allowed to be removed, " \
                     "with some positive penalty cost, if the constraints cannot be satisfied. Ideally, we would like the penalty to be 0, " \
                     "or otherwise as low as possible. \n" \
                     "- Your function is called convert. \n" \
                     "- The function takes as input a singular string called user_constraint_prompt \n" \
                     "- The function outputs a list of primitive predicates representing all of the constraints " \
                     "described in the prompt (where primitive means it is the most broken down version of the constraint) \n" \
                     "- Each predicate comes as a tuple containing a string representing the predicate, and a penalty " \
                     "value (-1 if not relaxable and higher if relaxable) \n" \
                     "- Format your output like this: (\"predicate1\", penalty1), ... \n" \
                     "- Your output should include NOTHING ELSE \n" \
                     "- You must determine, to the best of your judgement, which predicates are relaxable based on the user's prompt \n" \
                     "- If you deem a predicate relaxable, you must determine the positive penalty value on some scale " \
                     "(e.g if the constraint is important to the user and they choose to relax it if really necessary, " \
                     "penalty should be high. If the constraint is not important, meaning the user is willing to sacrifice " \
                     "it almost regardless, then penalty should be low) \n" \
                     "- The predicates you derive must include everything needed to constraint any arbitrary value in " \
                     "the universe to one that is satisfactory to the user. Include predicates that aren't directly " \
                     "mentioned but implied, such as the type of the value \n" \
                     "- You will be the one verifying these predicates against a given value, so choose a way of defining " \
                     "these predicates that leaves 0 ambiguity (if you are asked to verify the same value multiple times " \
                     "against the same predicate, the result should be deterministic) \n" \
                     "Here is the function call you are currently resolving: \n" \
                     "convert(\"{}\")".format(constraint_prompt)
    res: ollama.ChatResponse = ollama.chat(model, [convert_prompt])
    print(res.message.content)


def verify(predicate: str, val: str, model: str) -> bool:
    verify_prompt = "You are a service being used as part of a distributed software application. This service is run " \
                    "on every process in the network. You are responsible for processing a given input to a defined " \
                    "function and providing an output according to the function descriptions. For this reason, your " \
                    "reply must be exactly according to the output spec described. The application is a distributed " \
                    "constrained consensus solver. Users would like to coordinate with each other to agree on a value. " \
                    "Each user provides their constraints to their agent/process on what the value can be. These agents " \
                    "then communicate and arrive at consensus on a value that satisfies constraints. Some constraints " \
                    "can be specified as \"relaxable\", meaning they are allowed to be removed, with some positive penalty " \
                    "cost, if the constraints cannot be satisfied. Ideally, we would like the penalty to be 0, or " \
                    "otherwise as low as possible.

- Your function is called verify.
- The first input to the function is a string representing a constraint as a formal or semi-formal predicate
- The second input to the function is a value v represented as a string
- The function outputs “TRUE” if v satisfies the predicate
- The function outputs “FALSE” if v does not satisfy the predicate
- Your output should include the function output and NOTHING ELSE

Here is the function call you are currently resolving:

verify("PROMPT", “14:00”)
"


def evaluate_determinism():
    pass


MODEL = "gemma3"

response: ChatResponse = chat(model=MODEL, messages=[
    {"role": "user", "content": "Hi, this is a test. Please reply with 'I AM HERE' followed by three words of your choice"}
])

print(response)
