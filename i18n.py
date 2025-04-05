from pathlib import Path
import json

class I18nService:
    """ 国际化支持 """

    def __init__(self) -> None:
        # 默认语言设置为中文
        self._lang = "zh_CN"
        # 资源文件路径
        self._res_file = Path(__file__).parent / "res" / "i18n.json"
        
        # 如果资源文件不存在，则创建一个空的 JSON 文件
        if not self._res_file.exists():
            self._res_file.parent.mkdir(parents=True, exist_ok=True)
            self._res_file.touch()
            with open(self._res_file, "w", encoding="utf-8") as f:
                json.dump({"Version": "1.0.0", "Languages": {}}, f, ensure_ascii=False, indent=4)
        
        # 加载资源文件
        self._lang_dict = {}
        with open(self._res_file, "r", encoding="utf-8") as f:
            self._lang_dict = json.load(f).get("Languages", {})

    def set_lang(self, lang: str) -> None:
        """ 设置当前语言 """
        if lang in self._lang_dict:
            self._lang = lang
        else:
            raise ValueError(f"Unsupported language: {lang}")

    def get_text(self, key: str) -> str:
        """ 根据键获取翻译文本 """
        # 检查当前语言是否支持该键
        if self._lang in self._lang_dict and key in self._lang_dict[self._lang]:
            return self._lang_dict.get(self._lang, {}).get(key, key)
        else:
            # 如果没有找到翻译，返回键本身（作为默认值）
            return self._lang_dict.get("zh_CN", {}).get(key, key)

    def add_language(self, lang: str, translations: dict) -> None:
        """ 添加或更新一种语言的翻译 """
        if lang not in self._lang_dict:
            self._lang_dict[lang] = {}
        self._lang_dict[lang].update(translations)
        self._save_to_file()

    def _save_to_file(self) -> None:
        """ 将更新后的语言字典保存到文件 """
        data = {"Version": "1.0.0", "Languages": self._lang_dict}
        with open(self._res_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

# 测试
if __name__ == "__main__":
    i18n = I18nService()
    i18n.set_lang("en_US")
    print(i18n.get_text("page_title"))
    i18n.set_lang("zh_CN")
    print(i18n.get_text("page_title"))