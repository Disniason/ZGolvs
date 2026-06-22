import json
from openai import OpenAI
from typing import Dict, Any

from database.sql import sql
from database.db import async_database as db
from constant import subject_evaluter_api_config



class subject_evaluter:

    config = subject_evaluter_api_config
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"]
    )
    FULL_SCORE = 106.5  # 主观题固定满分

    @classmethod
    async def evaluate_subjective_answer(
        cls,
        standard_answer: str,
        user_answer: str
    ) -> Dict[str, Any]:
        # 前置空值校验
        user_answer = user_answer.strip()
        standard_answer = standard_answer.strip()
        if not user_answer:
            return {
                "code": 0,
                "msg": "用户作答内容不能为空",
                "data": None
            }
        if not standard_answer:
            return {
                "code": 0,
                "msg": "缺少标准参考答案，无法评分",
                "data": None
            }

        # 强约束提示词，强制固定结构JSON输出，保证分数准确
        system_prompt = f"""
你是严谨专业的大学英语阅卷老师，严格按照总分 {cls.FULL_SCORE} 分评判学生主观作答（作文/翻译），仅输出标准JSON，禁止额外文字、解释、注释。
评分分为5个维度，各维度满分固定：
1. 内容完整度：26.5分，考察是否覆盖题干全部要点、有无内容缺失
2. 逻辑结构：20分，段落衔接、行文条理、框架完整性
3. 语法准确度：22分，时态、单复数、固定搭配、从句等错误扣分
4. 词汇句式：22分，词汇多样性、高级句型、重复程度
5. 格式规范：16.5分，字数、分段、标点、大小写规范要求

硬性规则：
1. 总分 = 五个维度分数相加，总分不得超过{cls.FULL_SCORE}、不得低于0，保留1位小数；
2. 严格对照【标准范文】扣分，不得宽松打分；
3. 输出JSON仅包含以下字段：
{{
    "content": 内容得分(float),
    "logic": 逻辑得分(float),
    "grammar": 语法得分(float),
    "voc_sent": 词汇句式得分(float),
    "format": 格式得分(float),
    "total_score": 总分(float),
    "comment": 简短综合评价(80字内),
    "deduct_reason": 逐条写明扣分点
}}

【标准范文】
{standard_answer}
"""
        user_content = f"学生作答内容：\n{user_answer}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            # 调用硅基流动大模型接口
            response = cls.client.chat.completions.create(
                model=cls.config["model"],
                messages=messages,
                temperature=cls.config["temperature"],
                max_tokens=cls.config["max_tokens"],
                stream=cls.config["stream"],
                response_format={"type": "json_object"}  # 强制JSON返回，杜绝乱格式
            )
            # 提取AI返回内容
            raw_json_str = response.choices[0].message.content.strip()
            score_result = json.loads(raw_json_str)

            # 分数边界校正，确保不会超满分/负分，保证分数准确
            def fix_score(val, max_limit):
                num = float(val)
                if num < 0:
                    return 0.0
                if num > max_limit:
                    return max_limit
                return round(num, 1)

            score_result["content"] = fix_score(score_result.get("content", 0), 26.5)
            score_result["logic"] = fix_score(score_result.get("logic", 0), 20)
            score_result["grammar"] = fix_score(score_result.get("grammar", 0), 22)
            score_result["voc_sent"] = fix_score(score_result.get("voc_sent", 0), 22)
            score_result["format"] = fix_score(score_result.get("format", 0), 16.5)

            # 重新计算真实总分，覆盖模型可能输出错误的total_score
            real_total = round(
                score_result["content"]
                + score_result["logic"]
                + score_result["grammar"]
                + score_result["voc_sent"]
                + score_result["format"],
                1
            )
            if real_total > cls.FULL_SCORE:
                real_total = cls.FULL_SCORE
            score_result["total_score"] = real_total

            return {
                "code": 1,
                "msg": "评分完成",
                "data": score_result
            }

        except json.JSONDecodeError:
            return {
                "code": -1,
                "msg": "大模型返回格式错误，无法解析分数",
                "data": None
            }
        except Exception as e:
            return {
                "code": -99,
                "msg": f"评分接口异常：{str(e)}",
                "data": None
            }

    




class paper_exam:

    @classmethod
    async def get_paper_all_qid(cls, paper_name: str):
        # 获取试卷全部题目ID列表
        # 校验试卷是否存在
        check_sql = sql.check_name_paper_exists_sql()
        cnt = await db.execute_sql(check_sql, (paper_name,))
        cnt = cnt[0][0]
        if cnt == 0:
            return {"code":0, "msg":"该试卷不存在"}
        # 查询ID
        sql_str = sql.get_paper_all_question_id_list_sql(paper_name)
        rows = await db.execute_sql(sql_str)
        id_list = [row[0] for row in rows]
        return {
            "code":1,
            "msg":"查询成功",
            "data": id_list
        }


    @classmethod
    async def get_single_question_detail(cls, table_name: str, q_id: int):
        # 获取单题详情（考试用）
        check_sql = sql.check_name_paper_exists_sql()
        cnt = await db.execute_sql(check_sql, (table_name,))
        cnt = cnt[0][0]
        if cnt == 0:
            return {"code":0, "msg":"试卷不存在"}
        sql_str = sql.get_single_exam_question_sql(table_name)
        rows = await db.execute_sql(sql_str, (q_id,))
        if not rows:
            return {"code":0, "msg":"题目不存在"}
        r = rows[0]
        data = {
            "questionId": r[0],
            "question": r[1],
            "answer": r[2],
            "objective": bool(r[3]) if r[3] is not None else False
        }
        return {"code":1, "data": data}


    @classmethod
    async def batch_submit_exam_answer(cls, learner_id: int, paper_name: str, answer_list: list):
        # 批量保存用户考试答案
        if len(answer_list) == 0:
            return {"code":0, "msg":"无作答内容，无法交卷"}
        sql_str = sql.batch_save_user_exam_answer_sql()
        # 循环插入（简易实现，海量题目可优化批量）
        for item in answer_list:
            params = (
                learner_id,
                paper_name,
                item.questionId,
                item.userAnswer
            )
            await db.execute_sql(sql_str, params)
        return {"code":1, "msg":"交卷成功，答案已保存"}


    @classmethod
    async def get_all_paper_full_question(cls, paper_name: str):
        # 获取试卷全部题目完整信息（批改用：标准答案、分值、题型）
        check_sql = sql.check_name_paper_exists_sql()
        rows = await db.execute_sql(check_sql, (paper_name,))
        if rows[0][0] == 0:
            return {"code":0, "msg":"试卷不存在", "data":[]}
        sql_str = sql.get_question_all_info_sql(paper_name)
        q_rows = await db.execute_sql(sql_str)
        res = []
        paper_total_score = 0
        for r in q_rows:
            qid, q_text, std_ans, obj, s, paper_full = r
            paper_total_score = paper_full
            res.append({
                "questionId": qid,
                "question": q_text,
                "stdAnswer": std_ans,
                "objective": bool(obj),
                "score": float(s),
                "paperTotalScore": float(paper_full)
            })
        return {
            "code": 1,
            "paperFullScore": paper_total_score,
            "data": res
        }


    @classmethod
    async def judge_paper_all_answers(cls, paper_name: str, answer_list: list):
        """
        批量批改整套试卷
        :param paper_name: 试卷名称
        :param answer_list: [{questionId:int, userAnswer:str}]
        :return 批改明细+总分
        """
        # 1. 获取全量题目（含标准答案、每题分值、试卷总分）
        q_res = await cls.get_all_paper_full_question(paper_name)
        if q_res["code"] != 1:
            return q_res
        all_questions = q_res["data"]
        paper_full_score = q_res["paperFullScore"]

        # 转字典方便快速匹配 {questionId:题目对象}
        q_map = {item["questionId"]: item for item in all_questions}
        # 用户答案映射
        user_ans_map = {item.questionId: item.userAnswer for item in answer_list}

        judge_detail = []
        sum_total = 0.0

        # 2. 逐题批改
        for q in all_questions:
            qid = q["questionId"]
            std_ans = q["stdAnswer"]
            q_score = q["score"]
            is_obj = q["objective"]
            user_ans = user_ans_map.get(qid, "").strip()

            item = {
                "questionId": qid,
                "questionText": q["question"],
                "stdAnswer": std_ans,
                "userAnswer": user_ans,
                "isObjective": is_obj,
                "itemFullScore": q_score,
                "itemScore": 0.0,
                "aiComment": "",
                "deductReason": ""
            }

            if is_obj:
                # 客观题：直接比对
                if user_ans == std_ans.strip():
                    item["itemScore"] = q_score
                sum_total += item["itemScore"]
            else:
                # 主观题：调用AI打分
                eval_res = await subject_evaluter.evaluate_subjective_answer(std_ans, user_ans)
                if eval_res["code"] == 1:
                    ai_data = eval_res["data"]
                    item["itemScore"] = ai_data["total_score"]
                    item["aiComment"] = ai_data["comment"]
                    item["deductReason"] = ai_data["deduct_reason"]
                sum_total += item["itemScore"]
            judge_detail.append(item)

        return {
            "code": 1,
            "msg": "批改完成",
            "paperTotalScore": paper_full_score,
            "userTotalScore": round(sum_total, 1),
            "detailList": judge_detail
        }











