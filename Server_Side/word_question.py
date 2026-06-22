import os
import random
from typing import List, Dict
import redis.asyncio as redis
from datetime import datetime, timedelta

from database.sql import sql
from vocabulary import vocabulary
from constant import WORD_QUESTION_URL
from database.db import async_database as db


class NewRedisClient:
    
    HOST = os.getenv("REDIS_NEW_HOST", "127.0.0.1")
    PORT = int(os.getenv("REDIS_NEW_PORT", 6379))
    DB = int(os.getenv("REDIS_NEW_DB", 2))
    PWD = os.getenv("REDIS_NEW_PWD", "")

    _instance = None

    @classmethod
    async def get_conn(cls):
        if not cls._instance or not cls._instance.connection:
            cls._instance = redis.Redis(
                host=cls.HOST,
                port=cls.PORT,
                db=cls.DB,
                password=cls.PWD,
                decode_responses=True  # 自动解码字符串，不用手动bytes转换
            )
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.close()


class word_question:

    @staticmethod
    def get_today_expire_seconds() -> int:
        now = datetime.now()
        end = datetime(now.year, now.month, now.day, 23, 59, 59)
        delta = end - now
        return int(delta.total_seconds())


    @staticmethod
    def split_word_str(word_str: str) -> List[str]:
        """拆分数据库逗号拼接单词字符串为列表"""
        if not word_str:
            return []
        return [w.strip() for w in word_str.split(",") if w.strip()]
    

    @classmethod
    def join_word_list(cls, word_list: list):
        return ",".join(word_list)


    @classmethod
    async def check_daily_finish(cls, learner_id: int, vocab_id: int) -> dict:
        """
        检查用户该单词表今日是否全部学完
        返回：{code:1, is_finish:bool, msg:str}
        """
        redis_cli = await NewRedisClient.get_conn()
        finish_key = f"daily_finish:{learner_id}:{vocab_id}"
        val = await redis_cli.get(finish_key)
        is_finish = (val == "1")
        is_finish = False
        return {
            "code": 1,
            "is_finish": is_finish,
            "msg": "当日已完成全部单词学习" if is_finish else "未完成当日学习任务"
        }


    @classmethod
    async def refresh_daily_word_pool(cls, learner_id: int, vocab_id: int) -> dict:
        """
        从数据库unlearnedWords抽取dailyWordNum个乱序单词，写入Redis当日池子
        """
        try:
            # 1、查询用户单词本配置
            book_sql = sql.get_user_word_book_list_sql()
            book_rows = await db.execute_sql(book_sql, (learner_id,))
            target_book = None
            for row in book_rows:
                if row[1] == vocab_id:
                    target_book = row
                    break
            if not target_book:
                return {"code": 0, "msg": "未找到该单词表绑定记录"}

            learn_mode = target_book[4]
            daily_num = target_book[5]
            unlearn_str = target_book[3]
            vocab_table_id = vocab_id

            # 校验必须是乱序模式 learnMode=1(True)
            if learn_mode != 1:
                return {"code": 0, "msg": "当前为顺序背诵模式，不可使用乱序出题"}

            unlearn_list = cls.split_word_str(unlearn_str)
            if len(unlearn_list) == 0:
                return {"code": 0, "msg": "暂无未学习单词，请更换单词表"}
            # 随机抽取，数量不超过剩余未学总数
            pick_count = min(daily_num, len(unlearn_list))
            random.shuffle(unlearn_list)
            daily_word_list = unlearn_list[:pick_count]
            word_pool_str = ",".join(daily_word_list)

            # 2、写入Redis单词池，设置当日过期
            redis_cli = await NewRedisClient.get_conn()
            pool_key = f"daily_word_pool:{learner_id}:{vocab_id}"
            expire_sec = cls.get_today_expire_seconds()
            await redis_cli.setex(pool_key, expire_sec, word_pool_str)
            # 同时重置当日完成标记为0
            finish_key = f"daily_finish:{learner_id}:{vocab_id}"
            await redis_cli.setex(finish_key, expire_sec, "0")

            return {
                "code": 1,
                "daily_word_list": daily_word_list,
                "pick_num": pick_count,
                "msg": "当日单词池刷新成功"
            }
        except Exception as e:
            print("刷新当日单词池异常：", str(e))
            return {"code": 0, "msg": f"刷新失败：{str(e)}"}


    @classmethod
    async def get_valid_daily_word_pool(cls, learner_id: int, vocab_id: int) -> dict:
        """
        获取可用当日单词池：不存在/数量不对 → 自动刷新池子
        """
        # 先查是否当日已完成
        finish_check = await cls.check_daily_finish(learner_id, vocab_id)
        if finish_check["is_finish"]:
            return {"code": 0, "msg": finish_check["msg"]}

        # 读取Redis池子
        redis_cli = await NewRedisClient.get_conn()
        pool_key = f"daily_word_pool:{learner_id}:{vocab_id}"
        pool_str = await redis_cli.get(pool_key)

        # 读取配置里标准每日数量
        book_sql = sql.get_user_word_book_list_sql()
        book_rows = await db.execute_sql(book_sql, (learner_id,))
        target_daily_num = None
        for row in book_rows:
            if row[1] == vocab_id:
                target_daily_num = row[5]
                break
        if target_daily_num is None:
            return {"code": 0, "msg": "单词表配置不存在"}

        # 池子为空 / 单词数量不匹配 → 强制刷新
        need_refresh = False
        pool_word_list = []
        if not pool_str:
            need_refresh = True
        else:
            pool_word_list = cls.split_word_str(pool_str)
            if len(pool_word_list) != target_daily_num:
                need_refresh = True

        if need_refresh:
            refresh_res = await cls.refresh_daily_word_pool(learner_id, vocab_id)
            if refresh_res["code"] != 1:
                return refresh_res
            pool_word_list = refresh_res["daily_word_list"]

        return {
            "code": 1,
            "word_pool": pool_word_list,
            "daily_num": target_daily_num,
            "msg": "获取单词池成功"
        }


    
    @classmethod
    async def generate_sentence_choose_word_question(cls, learner_id: int, vocab_id: int, target_word: str) -> dict:
        #题型1：给例句，选择对应的单词（4选项：1正确释义，3干扰释义）
        #:param target_word: 池子内当前要出题的目标单词
        try:
            # 1、反查单词表真实物理表名（CET4/CET6）
            vocab_name_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_name_row = await db.execute_sql(vocab_name_sql, (vocab_id,))
            table_name = vocab_name_row[0][0]

            # 2、查询目标单词：释义 + 所有例句
            word_info_sql = sql.get_word_translations_examples_sql(table_name)
            word_row = await db.execute_sql(word_info_sql, (target_word,))
            if not word_row:
                return {"code": 0, "msg": f"单词{target_word}详情查询失败"}
            word, correct_meaning, all_example = word_row[0]

            # 随机选至少1个例句当题干
            example_list = [ex.strip() for ex in str(all_example).split("|") if ex.strip()]
            if not example_list:
                return {"code": 0, "msg": f"单词{target_word}无可用例句，无法出题"}
            random.shuffle(example_list)
            question_sentence = example_list[0]  # 取第一个随机例句作为题干

            # 3、从当日单词池里拿其他单词做干扰项（3个）
            pool_res = await cls.get_valid_daily_word_pool(learner_id, vocab_id)
            if pool_res["code"] != 1:
                return pool_res
            pool_words = pool_res["word_pool"]
            # 排除自身，剩下全部可当干扰源
            distractor_candidates = [w for w in pool_words if w != target_word]
            if len(distractor_candidates) < 3:
                # 池子内不够3个干扰，额外随机查表补充
                extra_distract_num = 3 - len(distractor_candidates)
                extra_sql = sql.batch_get_word_translations_sql(table_name, extra_distract_num)
                extra_rows = await db.execute_sql(extra_sql)
                for r in extra_rows:
                    distractor_candidates.append(r[0])

            # 4、批量获取干扰单词的释义
            distractor_meanings = []
            random.shuffle(distractor_candidates)
            pick_3_distract = distractor_candidates[:3]
            for d_word in pick_3_distract:
                d_row = await db.execute_sql(word_info_sql, (d_word,))
                if d_row:
                    distractor_meanings.append(d_row[0][1])

            # 5、组装4个选项：正确释义 + 3干扰释义，打乱顺序
            options = [correct_meaning] + distractor_meanings
            random.shuffle(options)
            correct_index = options.index(correct_meaning)

            # 题目结构返回
            return {
                "code": 1,
                "question_type": "sentence_choose_word",
                "target_word": target_word,
                "question_content": question_sentence,
                "option_list": options,
                "correct_index": correct_index,
                "correct_meaning": correct_meaning,
                "msg": "题目生成成功"
            }

        except Exception as e:
            print("生成例句选题异常：", str(e))
            return {"code": 0, "msg": f"出题失败：{str(e)}"}


    @classmethod
    async def generate_meaning_choose_word_question(cls, learner_id: int, vocab_id: int, target_word: str) -> dict:
        """
        题型2：根据中文释义选择单词
        题干：单词中文释义
        选项：4个单词拼写（来自当日单词池，含正确单词 + 3个干扰单词）
        """
        try:
            # 1. 获取当日合法单词池
            pool_res = await cls.get_valid_daily_word_pool(learner_id, vocab_id)
            if pool_res["code"] != 1:
                return pool_res
            word_pool = pool_res["word_pool"]

            # 2. 根据 vocab_id 查询单词表物理表名
            vocab_name_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_name_row = await db.execute_sql(vocab_name_sql, (vocab_id,))
            if not vocab_name_row:
                return {"code": 0, "msg": "未查询到单词表信息"}
            table_name = vocab_name_row[0][0]

            # 3. 查询目标单词的中文释义（作为题干）
            word_info_sql = sql.get_word_translations_examples_sql(table_name)
            target_row = await db.execute_sql(word_info_sql, (target_word,))
            if not target_row:
                return {"code": 0, "msg": f"单词 {target_word} 信息查询失败"}
            _, target_meaning, _ = target_row[0]

            # 4. 从当日单词池筛选干扰项（排除自身）
            distract_words = [w for w in word_pool if w != target_word]
            if len(distract_words) < 3:
                return {"code": 0, "msg": "当日单词数量不足，无法生成4选项题目"}

            # 随机取出 3 个干扰单词
            random.shuffle(distract_words)
            select_distract = distract_words[:3]

            # 5. 组装4个选项：正确单词 + 3个干扰单词，打乱顺序
            option_list = [target_word] + select_distract
            random.shuffle(option_list)
            correct_index = option_list.index(target_word)

            # 构造题目数据返回
            return {
                "code": 1,
                "question_type": "meaning_choose_word",
                "target_word": target_word,
                "question_content": target_meaning,
                "option_list": option_list,
                "correct_index": correct_index,
                "msg": "第二类题目生成成功"
            }

        except Exception as e:
            print("生成【中文选单词】题目异常：", str(e))
            return {"code": 0, "msg": f"出题失败：{str(e)}"}


    @classmethod
    async def generate_audio_choose_word_question(cls, learner_id: int, vocab_id: int, target_word: str) -> dict:
        try:
            pool_res = await cls.get_valid_daily_word_pool(learner_id, vocab_id)
            if pool_res["code"] != 1:
                return pool_res
            word_pool = pool_res["word_pool"]
            vocab_name_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_name_row = await db.execute_sql(vocab_name_sql, (vocab_id,))
            table_name = vocab_name_row[0][0]
            # 重点：音频题型必须调用查7个完整字段的get_full_word_detail_sql
            full_word_sql = sql.get_full_word_detail_sql(table_name)
            word_row = await db.execute_sql(full_word_sql, (target_word,))
            if not word_row:
                return {"code": 0, "msg": f"单词{target_word}数据查询失败"}
            # 完整7字段解包：word,translations,exchanges,examples,phonetic,uk_audio_path,us_audio_path
            word_spell, trans, exchanges, examples, phonetic, uk_audio, us_audio = word_row[0]
            audio_path_list = []
            if uk_audio:
                audio_path_list.append(uk_audio)
            if us_audio:
                audio_path_list.append(us_audio)
            if not audio_path_list:
                return {"code": 0, "msg": f"单词{target_word}无可用英/美音频文件"}
            select_audio_path = random.choice(audio_path_list)
            distract_words = [w for w in word_pool if w != target_word]
            if len(distract_words) < 3:
                return {"code": 0, "msg": "当日单词数量不足，无法生成4选项音频题目"}
            random.shuffle(distract_words)
            pick_distract = distract_words[:3]
            option_list = [target_word] + pick_distract
            random.shuffle(option_list)
            correct_index = option_list.index(target_word)
            return {
                "code": 1,
                "question_type": "audio_choose_word",
                "target_word": target_word,
                "audio_file_path": select_audio_path,
                "option_list": option_list,
                "correct_index": correct_index,
                "msg": "音频选题生成成功"
            }
        except Exception as e:
            print("音频选题生成异常:", str(e))
            return {"code": 0, "msg": f"出题失败:{str(e)}"}
        

    @classmethod
    async def generate_spell_choose_meaning_question(cls, learner_id: int, vocab_id: int, target_word: str) -> dict:
        try:
            pool_res = await cls.get_valid_daily_word_pool(learner_id, vocab_id)
            if pool_res["code"] != 1:
                return pool_res
            word_pool = pool_res["word_pool"]

            vocab_name_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_name_row = await db.execute_sql(vocab_name_sql, (vocab_id,))
            if not vocab_name_row:
                return {"code": 0, "msg": "未查询到单词表信息"}
            table_name = vocab_name_row[0][0]

            word_sql = sql.get_word_translations_examples_sql(table_name)
            target_row = await db.execute_sql(word_sql, (target_word,))
            if not target_row:
                return {"code": 0, "msg": f"单词{target_word}数据查询失败"}
            word_spell, target_trans, _ = target_row[0]

            distract_words = [w for w in word_pool if w != target_word]
            if len(distract_words) < 3:
                return {"code": 0, "msg": "当日单词数量不足，无法生成4选项题目"}
            random.shuffle(distract_words)
            pick_distract = distract_words[:3]

            distract_trans_list = []
            for d_word in pick_distract:
                d_row = await db.execute_sql(word_sql, (d_word,))
                if d_row:
                    distract_trans_list.append(d_row[0][1])

            option_list = [target_trans] + distract_trans_list
            random.shuffle(option_list)
            correct_index = option_list.index(target_trans)

            return {
                "code": 1,
                "question_type": "spell_choose_meaning",
                "target_word": target_word,
                "question_content": f"请选出单词 {word_spell} 的正确中文释义",
                "option_list": option_list,
                "correct_index": correct_index,
                "msg": "拼写选释义题目生成成功"
            }
        except Exception as e:
            print("拼写选释义题型生成异常:", str(e))
            return {"code": 0, "msg": f"出题失败:{str(e)}"}
        

    @classmethod
    async def get_word_full_detail(cls, learner_id: int, vocab_id: int, target_word: str) -> dict:
        try:
            vocab_name_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_name_row = await db.execute_sql(vocab_name_sql, (vocab_id,))
            table_name = vocab_name_row[0][0]
            full_sql = sql.get_full_word_detail_sql(table_name)
            row = await db.execute_sql(full_sql, (target_word,))
            if not row:
                return {"code":0, "msg":"单词详情不存在"}
            word,trans,exchanges,examples,phonetic,uk_audio,us_audio = row[0]
            return {
                "code":1,
                "data":{
                    "word":word,
                    "translations":trans,
                    "exchanges":exchanges,
                    "examples":examples,
                    "phonetic":phonetic,
                    "uk_audio_path":uk_audio,
                    "us_audio_path":us_audio
                },
                "msg":"查询单词详情成功"
            }
        except Exception as e:
            print("查询单词完整详情异常",str(e))
            return {"code":0,"msg":f"查询失败:{str(e)}"}


    @classmethod
    async def check_single_answer(cls, learner_id: int, vocab_id: int, target_word: str, user_select_index: int, real_correct_index: int) -> dict:
        is_correct = (user_select_index == real_correct_index)
        if is_correct:
            return {"code":1,"is_correct":True,"msg":"回答正确，进入下一题"}
        # 答错则返回完整单词详情
        detail_res = await cls.get_word_full_detail(learner_id, vocab_id, target_word)
        return {
            "code":1,
            "is_correct":False,
            "word_detail":detail_res["data"],
            "msg":"回答错误，请查看单词详情后继续"
        }


    @classmethod
    async def finish_daily_all_correct(cls, learner_id: int, vocab_id: int) -> dict:
        try:
            pool_res = await cls.get_valid_daily_word_pool(learner_id, vocab_id)
            if pool_res["code"] != 1:
                return pool_res
            daily_word_list = pool_res["word_pool"]
            daily_word_str = ",".join(daily_word_list)
            book_sql = sql.get_user_word_book_list_sql()
            book_rows = await db.execute_sql(book_sql, (learner_id,))
            old_learned = ""
            old_unlearned = ""
            for row in book_rows:
                if row[1] == vocab_id:
                    old_learned = row[2] or ""
                    old_unlearned = row[3] or ""
                    break
            new_learned = f"{old_learned},{daily_word_str}".strip(",")
            old_unlearn_arr = cls.split_word_str(old_unlearned)
            new_unlearn_arr = [w for w in old_unlearn_arr if w not in daily_word_list]
            new_unlearned = ",".join(new_unlearn_arr)
            update_sql = sql.update_word_learn_status_sql()
            await db.execute_sql(update_sql,(new_learned,new_unlearned,learner_id,vocab_id))
            redis_cli = await NewRedisClient.get_conn()
            expire_sec = cls.get_today_expire_seconds()
            finish_key = f"daily_finish:{learner_id}:{vocab_id}"
            await redis_cli.setex(finish_key, expire_sec, "1")
            return {
                "code": 1,
                "msg": "当日全部单词作答正确，学习进度已同步更新"
            }
        except Exception as e:
            print("完成当日学习同步异常：", str(e))
            return {"code": 0, "msg": f"同步进度失败：{str(e)}"}
        

    @classmethod
    async def get_word_book_words(cls, learner_id: int, vocab_id: int):
        get_sql = sql.get_word_book_words_sql(vocab_id, learner_id)
        rows = await db.execute_sql(get_sql, (vocab_id, learner_id))
        if not rows:
            return {"code": 0, "msg": "未查询到该单词本记录"}
        unlearn_str, learn_str = rows[0]
        unlearned = cls.split_word_str(unlearn_str)
        learned = cls.split_word_str(learn_str)
        return {
            "code": 1,
            "unlearnedWords": unlearned,
            "learnedWords": learned,
            "msg": "查询成功"
        }


    @classmethod
    async def move_word_to_learned(cls, learner_id: int, vocab_id: int, target_word: str):
        book_res = await cls.get_word_book_words(learner_id, vocab_id)
        if book_res["code"] != 1:
            return book_res
        unlearned = book_res["unlearnedWords"]
        learned = book_res["learnedWords"]
        if target_word not in unlearned:
            return {"code": 0, "msg": "该单词不在待背诵列表中"}
        unlearned.remove(target_word)
        learned.append(target_word)
        new_un = cls.join_word_list(unlearned)
        new_learn = cls.join_word_list(learned)
        update_sql = sql.update_word_book_words_sql(vocab_id, learner_id, new_un, new_learn)
        await db.execute_sql(update_sql, (new_un, new_learn, vocab_id, learner_id))
        return {"code": 1, "msg": "单词已移入已掌握列表"}


    @classmethod
    async def get_distract_words(cls, learner_id: int, vocab_id: int, exclude_word: str):
        book_res = await cls.get_word_book_words(learner_id, vocab_id)
        if book_res["code"] != 1:
            return []
        unlearned = [w for w in book_res["unlearnedWords"] if w != exclude_word]
        learned = book_res["learnedWords"]
        all_candidate = unlearned + learned
        random.shuffle(all_candidate)
        return all_candidate[:3]


    @classmethod
    async def gen_seq_sentence_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            word_sql = sql.get_word_translations_examples_sql(table_name)
            word_row = await db.execute_sql(word_sql, (target_word,))
            if not word_row:
                return {"code": 0, "msg": f"单词{target_word}不存在"}
            word, trans, examples = word_row[0]
            ex_list = [e.strip() for e in str(examples).split("|") if e.strip()]
            if not ex_list:
                return {"code": 0, "msg": "无例句无法出题"}
            pick_ex = random.choice(ex_list)
            distract_words = await cls.get_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) < 3:
                return {"code": 0, "msg": "单词总量不足，无法生成4选项"}
            dist_trans = []
            for w in distract_words:
                d_row = await db.execute_sql(word_sql, (w,))
                if d_row:
                    dist_trans.append(d_row[0][1])
            opt_list = [trans] + dist_trans
            random.shuffle(opt_list)
            correct_idx = opt_list.index(trans)
            return {
                "code":1,
                "question_type":"sentence_choose_word",
                "target_word":target_word,
                "question_content":pick_ex,
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("seq sentence q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}


    @classmethod
    async def gen_seq_meaning_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            word_sql = sql.get_word_translations_examples_sql(table_name)
            word_row = await db.execute_sql(word_sql, (target_word,))
            if not word_row:
                return {"code":0, "msg":f"单词{target_word}不存在"}
            _, trans, _ = word_row[0]
            distract_words = await cls.get_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) <3:
                return {"code":0, "msg":"单词总量不足"}
            opt_list = [target_word] + distract_words
            random.shuffle(opt_list)
            correct_idx = opt_list.index(target_word)
            return {
                "code":1,
                "question_type":"meaning_choose_word",
                "target_word":target_word,
                "question_content":trans,
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("seq meaning q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}


    @classmethod
    async def gen_seq_audio_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            full_sql = sql.get_full_word_detail_sql(table_name)
            word_row = await db.execute_sql(full_sql, (target_word,))
            if not word_row:
                return {"code":0, "msg":f"单词{target_word}不存在"}
            word_spell, trans, exchanges, examples, phonetic, uk_a, us_a = word_row[0]
            audio_pool = []
            if uk_a:
                audio_pool.append(uk_a)
            if us_a:
                audio_pool.append(us_a)
            if not audio_pool:
                return {"code":0, "msg":"无音频资源"}
            select_audio = random.choice(audio_pool)
            distract_words = await cls.get_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) <3:
                return {"code":0, "msg":"单词总量不足"}
            opt_list = [target_word] + distract_words
            random.shuffle(opt_list)
            correct_idx = opt_list.index(target_word)
            return {
                "code":1,
                "question_type":"audio_choose_word",
                "target_word":target_word,
                "audio_file_path":select_audio,
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("seq audio q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}

    # 7. 题型4 拼写选释义
    @classmethod
    async def gen_seq_spell_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            word_sql = sql.get_word_translations_examples_sql(table_name)
            word_row = await db.execute_sql(word_sql, (target_word,))
            if not word_row:
                return {"code":0, "msg":f"单词{target_word}不存在"}
            word_spell, trans, _ = word_row[0]
            distract_words = await cls.get_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) <3:
                return {"code":0, "msg":"单词总量不足"}
            dist_trans = []
            for w in distract_words:
                d_row = await db.execute_sql(word_sql, (w,))
                if d_row:
                    dist_trans.append(d_row[0][1])
            opt_list = [trans] + dist_trans
            random.shuffle(opt_list)
            correct_idx = opt_list.index(trans)
            return {
                "code":1,
                "question_type":"spell_choose_meaning",
                "target_word":target_word,
                "question_content":f"请选出单词 {word_spell} 的正确中文释义",
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("seq spell q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}


    @classmethod
    async def get_seq_word_detail(cls, learner_id: int, vocab_id: int, target_word: str):
        vocab_sql = sql.get_vocab_table_name_by_id_sql()
        vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
        table_name = vocab_row[0][0]
        full_sql = sql.get_full_word_detail_sql(table_name)
        row = await db.execute_sql(full_sql, (target_word,))
        if not row:
            return {"code":0, "msg":"单词不存在"}
        word,trans,exchanges,examples,phonetic,uk,us = row[0]
        return {
            "code":1,
            "data":{
                "word":word,
                "translations":trans,
                "exchanges":exchanges,
                "examples":examples,
                "phonetic":phonetic,
                "uk_audio_path":uk,
                "us_audio_path":us
            }
        }


    @classmethod
    async def check_seq_answer(cls, learner_id: int, vocab_id: int, target_word: str, user_idx: int, real_idx: int):
        correct = (user_idx == real_idx)
        if correct:
            return {"code":1, "is_correct":True, "msg":"回答正确"}
        detail_res = await cls.get_seq_word_detail(learner_id, vocab_id, target_word)
        return {
            "code":1,
            "is_correct":False,
            "word_detail":detail_res["data"],
            "msg":"回答错误"
        }


    @classmethod
    async def move_word_back_unlearned(cls, learner_id: int, vocab_id: int, target_word: str):
        book_res = await cls.get_word_book_words(learner_id, vocab_id)
        if book_res["code"] != 1:
            return book_res
        unlearned = book_res["unlearnedWords"]
        learned = book_res["learnedWords"]
        if target_word not in learned:
            return {"code": 0, "msg": "该单词不在已掌握列表中"}
        learned.remove(target_word)
        unlearned.append(target_word)
        new_un = cls.join_word_list(unlearned)
        new_learn = cls.join_word_list(learned)
        move_sql = sql.move_word_back_to_unlearned_sql(vocab_id, learner_id, new_un, new_learn)
        await db.execute_sql(move_sql, (new_un, new_learn, vocab_id, learner_id))
        return {"code": 1, "msg": "单词移回待背诵列表"}


    @classmethod
    async def get_test_distract_words(cls, learner_id: int, vocab_id: int, exclude_word: str):
        book_res = await cls.get_word_book_words(learner_id, vocab_id)
        if book_res["code"] != 1:
            return []
        learned = [w for w in book_res["learnedWords"] if w != exclude_word]
        unlearned = book_res["unlearnedWords"]
        all_candidate = learned + unlearned
        random.shuffle(all_candidate)
        return all_candidate[:3]


    @classmethod
    async def gen_test_sentence_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            word_sql = sql.get_word_translations_examples_sql(table_name)
            word_row = await db.execute_sql(word_sql, (target_word,))
            if not word_row:
                return {"code": 0, "msg": f"单词{target_word}不存在"}
            word, trans, examples = word_row[0]
            ex_list = [e.strip() for e in str(examples).split("|") if e.strip()]
            if not ex_list:
                return {"code": 0, "msg": "无例句无法出题"}
            pick_ex = random.choice(ex_list)
            distract_words = await cls.get_test_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) < 3:
                return {"code": 0, "msg": "单词总量不足，无法生成4选项"}
            dist_trans = []
            for w in distract_words:
                d_row = await db.execute_sql(word_sql, (w,))
                if d_row:
                    dist_trans.append(d_row[0][1])
            opt_list = [trans] + dist_trans
            random.shuffle(opt_list)
            correct_idx = opt_list.index(trans)
            return {
                "code":1,
                "question_type":"sentence_choose_word",
                "target_word":target_word,
                "question_content":pick_ex,
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("test sentence q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}


    @classmethod
    async def gen_test_meaning_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            word_sql = sql.get_word_translations_examples_sql(table_name)
            word_row = await db.execute_sql(word_sql, (target_word,))
            if not word_row:
                return {"code":0, "msg":f"单词{target_word}不存在"}
            _, trans, _ = word_row[0]
            distract_words = await cls.get_test_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) <3:
                return {"code":0, "msg":"单词总量不足"}
            opt_list = [target_word] + distract_words
            random.shuffle(opt_list)
            correct_idx = opt_list.index(target_word)
            return {
                "code":1,
                "question_type":"meaning_choose_word",
                "target_word":target_word,
                "question_content":trans,
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("test meaning q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}


    @classmethod
    async def gen_test_audio_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            full_sql = sql.get_full_word_detail_sql(table_name)
            word_row = await db.execute_sql(full_sql, (target_word,))
            if not word_row:
                return {"code":0, "msg":f"单词{target_word}不存在"}
            word_spell, trans, exchanges, examples, phonetic, uk_a, us_a = word_row[0]
            audio_pool = []
            if uk_a:
                audio_pool.append(uk_a)
            if us_a:
                audio_pool.append(us_a)
            if not audio_pool:
                return {"code":0, "msg":"无音频资源"}
            select_audio = random.choice(audio_pool)
            distract_words = await cls.get_test_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) <3:
                return {"code":0, "msg":"单词总量不足"}
            opt_list = [target_word] + distract_words
            random.shuffle(opt_list)
            correct_idx = opt_list.index(target_word)
            return {
                "code":1,
                "question_type":"audio_choose_word",
                "target_word":target_word,
                "audio_file_path":select_audio,
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("test audio q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}


    @classmethod
    async def gen_test_spell_q(cls, learner_id: int, vocab_id: int, target_word: str):
        try:
            vocab_sql = sql.get_vocab_table_name_by_id_sql()
            vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
            table_name = vocab_row[0][0]
            word_sql = sql.get_word_translations_examples_sql(table_name)
            word_row = await db.execute_sql(word_sql, (target_word,))
            if not word_row:
                return {"code":0, "msg":f"单词{target_word}不存在"}
            word_spell, trans, _ = word_row[0]
            distract_words = await cls.get_test_distract_words(learner_id, vocab_id, target_word)
            if len(distract_words) <3:
                return {"code":0, "msg":"单词总量不足"}
            dist_trans = []
            for w in distract_words:
                d_row = await db.execute_sql(word_sql, (w,))
                if d_row:
                    dist_trans.append(d_row[0][1])
            opt_list = [trans] + dist_trans
            random.shuffle(opt_list)
            correct_idx = opt_list.index(trans)
            return {
                "code":1,
                "question_type":"spell_choose_meaning",
                "target_word":target_word,
                "question_content":f"请选出单词 {word_spell} 的正确中文释义",
                "option_list":opt_list,
                "correct_index":correct_idx,
                "msg":"出题成功"
            }
        except Exception as e:
            print("test spell q err:", str(e))
            return {"code":0, "msg":f"出题失败:{str(e)}"}


    """
    @classmethod
    async def get_seq_word_detail(cls, learner_id: int, vocab_id: int, target_word: str):
        vocab_sql = sql.get_vocab_table_name_by_id_sql()
        vocab_row = await db.execute_sql(vocab_sql, (vocab_id,))
        table_name = vocab_row[0][0]
        full_sql = sql.get_full_word_detail_sql(table_name)
        row = await db.execute_sql(full_sql, (target_word,))
        if not row:
            return {"code":0, "msg":"单词不存在"}
        word,trans,exchanges,examples,phonetic,uk,us = row[0]
        return {
            "code":1,
            "data":{
                "word":word,
                "translations":trans,
                "exchanges":exchanges,
                "examples":examples,
                "phonetic":phonetic,
                "uk_audio_path":uk,
                "us_audio_path":us
            }
        }
    """


    @classmethod
    async def check_test_answer(cls, learner_id: int, vocab_id: int, target_word: str, user_idx: int, real_idx: int):
        correct = (user_idx == real_idx)
        if correct:
            return {"code":1, "is_correct":True, "msg":"回答正确"}
        detail_res = await cls.get_seq_word_detail(learner_id, vocab_id, target_word)
        return {
            "code":1,
            "is_correct":False,
            "word_detail":detail_res["data"],
            "msg":"回答错误"
        }








