import csv, ast, os

def tokenize(sentence: str):
    """中文句子=>字元清單（保留所有標點符號）"""
    return list(sentence.strip())

def tag_sentence(sentence: str, ing_list):
    """
    把 sentence 切成 tokens，對照 ing_list 產生 BIO tag。
    只吃到 ingredients 完整連續字元才標註，避免『雞』吃掉『雞蛋』。
    """
    tokens = tokenize(sentence)
    tags   = ["O"] * len(tokens)
    joined = "".join(tokens)

    for ing in sorted((i.strip() for i in ing_list if i.strip()), key=len, reverse=True):
        start = 0
        while True:
            idx = joined.find(ing, start)
            if idx == -1:
                break
            end = idx + len(ing)
            if all(t == "O" for t in tags[idx:end]):
                tags[idx] = "B-INGREDIENT"
                for j in range(idx + 1, end):
                    tags[j] = "I-INGREDIENT"
            start = end
    return tokens, tags

def convert_csv_to_slot(csv_path="fine_tune_data.csv",
                        out_path="BIO1.txt",
                        encoding="utf-8"):

    with open(csv_path, newline="", encoding=encoding) as f_in, \
        open(out_path, "w", encoding=encoding) as f_out:

        reader = csv.DictReader(f_in)
        for row in reader:
            sentence   = row["sentence"]
            ingredients = ast.literal_eval(row["ingredients"])

            tokens, tags = tag_sentence(sentence, ingredients)

            for tok, tag in zip(tokens, tags):
                if tok.strip():
                    f_out.write(f"{tok} {tag}\n")
            f_out.write("\n")

    print(f"轉換完成：{os.path.abspath(out_path)}")

if __name__ == "__main__":
    convert_csv_to_slot()