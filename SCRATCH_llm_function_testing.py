import ollama
from abc import abstractmethod


def file_to_string(filepath: str):
    with open(filepath, "r") as file:
        s = file.read()
    return s


class OllamaLLM:
    def __init__(self, convert_filepath: str, verify_filepath: str, model: str):
        self.__convert_filepath = convert_filepath
        self.__verify_filepath = verify_filepath
        self.__model = model

        self.__convert_prompt = file_to_string(self.__convert_filepath)
        self.__verify_prompt = file_to_string(self.__verify_filepath)

    def convert(self, constraint_prompt: str) -> list[tuple[str, int]]:
        res: ollama.ChatResponse = ollama.chat(model=self.__model, messages=[{"role": "user", "content": self.__convert_prompt.format(constraint_prompt)}])
        print(res.message.content)
        return []

    def verify(self, predicate: str, val: str) -> bool:
        res: ollama.ChatResponse = ollama.chat(model=self.__model, messages=[{"role": "user", "content": self.__verify_prompt.format(predicate, val)}])
        print(res.message.content)
        return False

    def evaluate_determinism(self, predicate: str, val: str, count: int, print_result: bool = True) -> tuple[int, int]:
        """ verify a given predicate with a given value using a given model count number of times and return how many times TRUE
        returned and how many times FALSE returned. Also print analysis if desired """
        num_true = 0
        num_false = 0
        for _ in range(count):
            if self.verify(predicate, val):
                num_true += 1
            else:
                num_false += 1
        total = num_true + num_false
        if print_result:
            print(f"Verify returned {(str(True) if num_true > num_false else str(False)).upper()} "
                  f"{(max(num_false, num_true) / total) * 100}% of the time")
        return num_true, num_false


GPTOSS_V1 = OllamaLLM("./prompts/CONVERT_V1", "./prompts/VERIFY_V1", "gpt-oss")

if __name__ == "__main__":
    GPTOSS_V1.convert(file_to_string("./prompts/v1_prompts/lunch_meet/PROMPT_1"))
