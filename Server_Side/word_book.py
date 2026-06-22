import math

from database.sql import sql
from vocabulary import vocabulary
from database.db import async_database as db


class word_book:

    @classmethod
    async def add_vocabulary_to_book(cls, learner_id: int, vocab_id: int, vocab_table_name: str):
        try:
            # 1、查重：用户是否已绑定该单词表
            check_exist_sql = sql.check_word_book_exists_sql()
            exist_rows = await db.execute_sql(check_exist_sql, (learner_id, vocab_id))
            if exist_rows[0][0] > 0:
                # 精准重复提示
                return {"code": 0, "msg": "重复添加：该单词表已存在于你的单词本中"}

            # 2、复用查询单词拼写
            spell_res = await vocabulary.get_table_word_spell_list(vocab_table_name)
            """print("单词查询结果：", spell_res)
            spell_list = spell_res["spell_list"]
            print("单词列表数组：", spell_list)
            unlearned_str = ",".join(spell_list)
            print("拼接后的未学单词字符串：", unlearned_str)"""

            if spell_res["code"] != 1:
                return spell_res

            spell_list = spell_res["spell_list"]
            unlearned_str = ",".join(spell_list)
            learned_str = ""
            learn_mode = 0
            daily_word_num = 10

            # 3、插入数据
            insert_sql = sql.insert_word_book_sql()
            await db.execute_sql(insert_sql, (learner_id, vocab_id, learned_str, unlearned_str, learn_mode, daily_word_num))
            return {"code": 1, "msg": "添加单词表到单词本成功"}

        except Exception as e:
            print(f"【单词本添加异常】{str(e)}")
            # 数据库约束异常捕获（复合主键冲突兜底）
            if "duplicate key" in str(e).lower() or "唯一约束" in str(e):
                return {"code": 0, "msg": "重复添加：该单词表已存在于你的单词本中"}
            return {"code": 0, "msg": f"服务器操作异常：{str(e)}"}
        

    @classmethod
    async def get_user_all_word_books(cls, learner_id: int):
        """
        查询登录用户单词本内所有单词表（联查名称+学习配置）
        :param learner_id: 当前登录学习用户ID（由Token解析）
        :return: {code:int, data:列表, msg:str}
        """
        try:
            get_word_book_sql = sql.get_user_word_book_list_sql()
            rows = await db.execute_sql(get_word_book_sql, (learner_id,))
            res_list = []
            for row in rows:
                res_list.append({
                    "learnerId": row[0],
                    "vocabularyId": row[1],
                    "learnedWords": row[2] if row[2] else "",
                    "unlearnedWords": row[3] if row[3] else "",
                    "learnMode": row[4],
                    "dailyWordNum": row[5],
                    "vocabularyName": row[6] if row[6] else "未知单词表"
                })
            return {
                "code": 1,
                "data": res_list,
                "msg": "查询用户单词本列表成功"
            }
        except Exception as e:
            print("查询用户单词本异常：", str(e))
            return {
                "code": 0,
                "data": [],
                "msg": f"数据库查询失败：{str(e)}"
            }
        

    @classmethod
    async def get_word_book_config(cls, learner_id: int, vocab_id: int):
        """
        获取单词表当前配置：学习模式、每日单词数
        """
        try:
            get_config_sql = sql.get_word_book_config_sql()
            rows = await db.execute_sql(get_config_sql, (learner_id, vocab_id))
            if not rows:
                return {"code": 0, "msg": "未找到该单词表配置"}

            return {
                "code": 1,
                "data": {
                    "learnMode": rows[0][0],
                    "dailyWordNum": rows[0][1]
                },
                "msg": "查询配置成功"
            }
        except Exception as e:
            print("查询配置异常：", str(e))
            return {"code": 0, "msg": f"查询失败：{str(e)}"}


    @classmethod
    async def update_word_book_config(cls, learner_id: int, vocab_id: int, learn_mode: int, daily_num: int):
        """
        更新单词表配置
        :param learn_mode: 0=顺序模式  1=乱序模式
        :param daily_num: 每日背诵数量（做简单数值校验）
        """
        try:
            # 基础数值校验
            if learn_mode not in (0, 1):
                return {"code": 0, "msg": "学习模式只能选择 顺序(0) 或 乱序(1)"}
            if not (10 <= daily_num <= 200):
                return {"code": 0, "msg": "每日单词数量范围：10 ~ 200"}

            update_config_sql = sql.update_word_book_config_sql()
            learn_mode = True if learn_mode else False
            #print(learn_mode)
            await db.execute_sql(update_config_sql, (learn_mode, daily_num, learner_id, vocab_id))
            return {"code": 1, "msg": "配置修改成功"}
        except Exception as e:
            print("更新配置异常：", str(e))
            return {"code": 0, "msg": f"修改失败：{str(e)}"}
        

    @classmethod
    async def get_learner_wordbook_list(cls, learner_id: int):
        # 获取当前用户全部绑定单词本
        sql_str = sql.get_learner_all_wordbook_sql()
        rows = await db.execute_sql(sql_str, (learner_id,))
        res_list = []
        for row in rows:
            res_list.append({
                "vocabularyId": row[0],
                "vocabularyName": row[1]
            })
        return {
            "code": 1,
            "msg": "查询成功",
            "data": res_list
        }


    @classmethod
    async def unbind_vocabulary(cls, learner_id: int, vocab_id: int):
        # 用户解绑单词本，删除关联记录
        sql_str = sql.unbind_wordbook_sql()
        affect = await db.execute_sql(sql_str, (learner_id, vocab_id))
        if affect > 0:
            return {"code": 1, "msg": "已解除单词本绑定"}
        else:
            return {"code": 0, "msg": "未查询到该绑定关系，解绑失败"}



class word_book_analyze:

    @staticmethod
    def split_word_str(word_str: str) -> list:
        if not word_str:
            return []
        return [w.strip() for w in word_str.split(",") if w.strip()]


    @classmethod
    async def get_single_book_data(cls, learner_id: int, vocab_id: int):
        single_sql = sql.get_single_book_analyze_sql()
        row = await db.execute_sql(single_sql, (learner_id, vocab_id))
        if not row:
            return {"code": 0, "msg": "无该单词本数据"}
        learned_str, unlearn_str, learn_mode, daily_num = row[0][1], row[0][2], row[0][3], row[0][4]
        learned = cls.split_word_str(learned_str)
        unlearned = cls.split_word_str(unlearn_str)
        total_all = len(learned) + len(unlearned)
        learned_count = len(learned)
        unlearn_count = len(unlearned)
        master_rate = round((learned_count / total_all * 100) if total_all > 0 else 0, 2)

        # 每日学习预测：按每日计划量计算剩余完成天数
        remain_days = math.ceil(unlearn_count / daily_num) if daily_num > 0 else 999
        mode_text = "顺序背诵" if learn_mode == 0 else "乱序背诵"

        return {
            "code": 1,
            "base": {
                "vocabularyId": vocab_id,
                "learnModeText": mode_text,
                "dailyPlanNum": daily_num,
                "totalWordCount": total_all,
                "learnedCount": learned_count,
                "unlearnedCount": unlearn_count,
                "masterRate": master_rate,
                "predictFinishDays": remain_days
            },
            "chart_pie": [
                {"name": "已掌握单词", "value": learned_count},
                {"name": "待背诵单词", "value": unlearn_count}
            ],
            "word_list": {
                "learned": learned,
                "unlearned": unlearned
            }
        }


    @classmethod
    async def get_all_user_books_compare(cls, learner_id: int):
        list_sql = sql.get_all_user_book_list_sql()
        rows = await db.execute_sql(list_sql, (learner_id,))
        if not rows:
            return {"code": 0, "msg": "暂无单词本数据"}
        chart_bar = []
        table_list = []
        for r in rows:
            vocab_id, vocab_name, learned_str, unlearn_str, mode, daily = r
            l = cls.split_word_str(learned_str)
            u = cls.split_word_str(unlearn_str)
            l_cnt = len(l)
            u_cnt = len(u)
            total = l_cnt + u_cnt
            rate = round((l_cnt / total * 100) if total > 0 else 0, 2)
            chart_bar.append({
                "bookName": vocab_name,
                "learned": l_cnt,
                "unlearned": u_cnt,
                "masterRate": rate
            })
            table_list.append({
                "vocabularyName": vocab_name,
                "total": total,
                "learned": l_cnt,
                "unlearned": u_cnt,
                "dailyPlan": daily,
                "mode": "顺序" if mode == 0 else "乱序",
                "masterRate": f"{rate}%"
            })
        return {
            "code": 1,
            "barChartData": chart_bar,
            "tableData": table_list
        }


    @classmethod
    async def get_daily_predict_info(cls, learner_id: int, vocab_id: int):
        target_sql = sql.get_book_daily_target_sql()
        row = await db.execute_sql(target_sql, (learner_id, vocab_id))
        if not row:
            return {"code": 0, "msg": "数据不存在"}
        daily_num, un_str = row[0][0], row[0][1]
        un_list = cls.split_word_str(un_str)
        un_cnt = len(un_list)
        today_remain = un_cnt % daily_num
        need_today = today_remain if today_remain != 0 else daily_num
        total_days = math.ceil(un_cnt / daily_num)
        return {
            "code": 1,
            "predict": {
                "dailyPlan": daily_num,
                "unlearnTotal": un_cnt,
                "todayNeedLearn": need_today,
                "allFinishDays": total_days,
                "isAdequate": need_today <= daily_num
            }
        }


