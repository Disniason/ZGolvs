import os
import json
from tqdm import tqdm

from .constant import *


class endict_raw:

    def __init__(self, data_dir : str = '.'):
        self.data_dir = data_dir
        self.audio_path = os.path.abspath(os.path.join(self.data_dir, 'audio'))
        self.dict_path = os.path.abspath(os.path.join(self.data_dir, 'dict'))
        self.vocabulary_path = os.path.abspath(os.path.join(self.data_dir, 'vocabulary'))

        self.exchange_map = {
            'd': '过去式',
            'p': '过去分词',
            'i': '现在分词',
            '3': '第三人称单数',
            's': '复数',
            '0': '词根基础词',
            '1': '词尾变化后缀'
        }

        self.audio_uk_path = os.path.abspath(os.path.join(self.audio_path, 'uk'))
        dict_uk_audios_path = {}
        for file_name in os.listdir(self.audio_uk_path):
            if file_name.endswith(".mp3"):
                word = file_name[0 : file_name.find(".mp3") : 1]
                file_path = os.path.abspath(os.path.join(self.audio_uk_path, file_name))
                dict_uk_audios_path[word] = file_path

        self.audio_us_path = os.path.abspath(os.path.join(self.audio_path, 'us'))
        dict_us_audios_path = {}
        for file_name in os.listdir(self.audio_us_path):
            if file_name.endswith(".mp3"):
                word = file_name[0 : file_name.find(".mp3") : 1]
                file_path = os.path.abspath(os.path.join(self.audio_us_path, file_name))
                dict_us_audios_path[word] = file_path

        dict_jsons_path = []
        for file_name in os.listdir(self.dict_path):
            if file_name.endswith(".json"):
                file_path = os.path.abspath(os.path.join(self.dict_path, file_name))
                dict_jsons_path.append(file_path)

        self.all_words = {}
        for file_path in tqdm(dict_jsons_path, total = len(dict_jsons_path)):
            with open(file_path, "r", encoding = "utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    word_dict = json.loads(line)
                    word = word_dict["word"]
                    lower_word = word.lower()
                    translation = word_dict["translation"]
                    exchange = word_dict["exchange"]
                    exchanges = {}
                    for _ in exchange:
                        pos = _.find(':')
                        exchange_key = _[0:pos:1]
                        exchange_key = self.exchange_map.get(exchange_key, exchange_key)
                        exchange_value = _[pos + 1 : len(_) : 1]
                        exchanges[exchange_key] = exchange_value
                    examples = word_dict["examples"]
                    phonetic = word_dict["phonetic"]
                    uk_audio_path = dict_uk_audios_path.get(lower_word, '')
                    us_audio_path = dict_us_audios_path.get(lower_word, '')
                    self.all_words[lower_word] = {
                        'word': word,
                        'translations': translation,
                        'exchanges': exchanges,
                        'examples': examples,
                        'phonetic': phonetic,
                        'uk_audio_path': uk_audio_path,
                        'us_audio_path': us_audio_path
                    }

        self.all_words_path = os.path.abspath(os.path.join(self.data_dir, 'endict_all_words.json'))
        with open(self.all_words_path, "w", encoding = "utf-8") as f:
            json.dump(
                self.all_words,
                f,
                ensure_ascii = False,
                indent = 4
            )


    def __len__(self):
        return len(self.all_words)



class endict_raw_cet4():
    def __init__(self, endict_raw):

        self.raw_json_path = os.path.abspath(os.path.join(endict_raw.vocabulary_path, 'cet4.json'))
        with open(self.raw_json_path, "r", encoding = "utf-8") as f:
            self.words = json.load(f)
        self.words.sort(key = lambda x : x.lower())

        self.words_dict = {}
        for word in tqdm(self.words, total = len(self.words)):
            lower_word = word.lower()
            word_dict = endict_raw.all_words.get(lower_word, dict())
            self.words_dict[word] = word_dict

        self.all_words_path = os.path.abspath(os.path.join(endict_raw.data_dir, 'endict_cet4_all_words.json'))
        with open(self.all_words_path, "w", encoding = "utf-8") as f:
            json.dump(
                self.words_dict,
                f,
                ensure_ascii = False,
                indent = 4
            )


    def __len__(self):
        return len(self.words_dict)
    

    def __getitem__(self, index):
        index %= self.__len__()
        word = self.words[index]
        return self.words_dict[word]
    


class endict_raw_cet6():
    def __init__(self, endict_raw):

        self.raw_json_path = os.path.abspath(os.path.join(endict_raw.vocabulary_path, 'cet6.json'))
        with open(self.raw_json_path, "r", encoding = "utf-8") as f:
            self.words = json.load(f)
        self.words.sort(key = lambda x : x.lower())

        self.words_dict = {}
        for word in tqdm(self.words, total = len(self.words)):
            lower_word = word.lower()
            word_dict = endict_raw.all_words.get(lower_word, dict())
            self.words_dict[word] = word_dict

        self.all_words_path = os.path.abspath(os.path.join(endict_raw.data_dir, 'endict_cet6_all_words.json'))
        with open(self.all_words_path, "w", encoding = "utf-8") as f:
            json.dump(
                self.words_dict,
                f,
                ensure_ascii = False,
                indent = 4
            )


    def __len__(self):
        return len(self.words_dict)
    

    def __getitem__(self, index):
        index %= self.__len__()
        word = self.words[index]
        return self.words_dict[word]
    


class endict_raw_gaozhong():
    def __init__(self, endict_raw):

        self.raw_json_path = os.path.abspath(os.path.join(endict_raw.vocabulary_path, 'gaozhong.json'))
        with open(self.raw_json_path, "r", encoding = "utf-8") as f:
            self.words = json.load(f)
        self.words.sort(key = lambda x : x.lower())

        self.words_dict = {}
        for word in tqdm(self.words, total = len(self.words)):
            lower_word = word.lower()
            word_dict = endict_raw.all_words.get(lower_word, dict())
            self.words_dict[word] = word_dict

        self.all_words_path = os.path.abspath(os.path.join(endict_raw.data_dir, 'endict_gaozhong_all_words.json'))
        with open(self.all_words_path, "w", encoding = "utf-8") as f:
            json.dump(
                self.words_dict,
                f,
                ensure_ascii = False,
                indent = 4
            )


    def __len__(self):
        return len(self.words_dict)
    

    def __getitem__(self, index):
        index %= self.__len__()
        word = self.words[index]
        return self.words_dict[word]
    


def init_endict():
    er = endict_raw(endict_raw_path)
    er_cet4 = endict_raw_cet4(er)
    er_cet6 = endict_raw_cet6(er)
    er_gaozhong = endict_raw_gaozhong(er)



class endict_cet4:

    def __init__(self, json_path):
        self.json_path = json_path

        with open(self.json_path, "r", encoding = "utf-8") as f:
            self.all_words_dict = json.load(f)

        self.all_words_ordered_list = [_ for _ in self.all_words_dict.keys()]


    def __len__(self):
        return len(self.all_words_dict)
    

    def __getitem__(self, index):
        index %= self.__len__()
        word = self.all_words_ordered_list[index]
        return self.all_words_dict[word]
    


class endict_cet6:

    def __init__(self, json_path):
        self.json_path = json_path

        with open(self.json_path, "r", encoding = "utf-8") as f:
            self.all_words_dict = json.load(f)

        self.all_words_ordered_list = [_ for _ in self.all_words_dict.keys()]


    def __len__(self):
        return len(self.all_words_dict)
    

    def __getitem__(self, index):
        index %= self.__len__()
        word = self.all_words_ordered_list[index]
        return self.all_words_dict[word]



class endict_gaozhong:

    def __init__(self, json_path):
        self.json_path = json_path

        with open(self.json_path, "r", encoding = "utf-8") as f:
            self.all_words_dict = json.load(f)

        self.all_words_ordered_list = [_ for _ in self.all_words_dict.keys()]


    def __len__(self):
        return len(self.all_words_dict)
    

    def __getitem__(self, index):
        index %= self.__len__()
        word = self.all_words_ordered_list[index]
        return self.all_words_dict[word]
