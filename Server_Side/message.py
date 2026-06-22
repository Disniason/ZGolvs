



from database.sql import sql
from database.db import async_database as db


class message:

    pass








class feedback_reply(message):

    @classmethod
    async def add_feedback(cls, learner_id: int, content: str):
        if not content or len(content) < 2:
            return {"code": 0, "msg": "反馈内容不能为空"}

        sql_str = sql.insert_feedback_sql()
        result = await db.execute_sql(sql_str, (learner_id, content))

        # result 受影响行数 > 0 代表成功
        if result:
            return {"code": 1, "msg": "反馈提交成功，等待管理员回复"}
        else:
            return {"code": 0, "msg": "反馈提交失败"}


    # 用户查询自己的所有反馈 & 回复
    @classmethod
    async def get_my_feedbacks(cls, learner_id: int):
        sql_str = sql.get_learner_feedbacks_sql()
        rows = await db.execute_sql(sql_str, (learner_id,))

        feedback_list = []
        for row in rows:
            feedback_list.append({
                "feedbackId": row[0],
                "learnerId": row[1],
                "sendTime": row[2],
                "content": row[3],
                "replied": bool(row[4]),
                "replyContent": row[5] if row[5] else "未回复",
                "replyTime": row[6] if row[6] else None,
                "adminId": row[7] if row[7] else None
            })

        return {"code": 1, "data": feedback_list}
    

    @classmethod
    async def get_unreplied_feedbacks(cls):
        sql_str = sql.get_unreplied_feedbacks_sql()
        rows = await db.execute_sql(sql_str)
        feedback_list = []
        for row in rows:
            content_raw = row[3]
            short_content = content_raw[:30] + "..." if len(content_raw) > 30 else content_raw
            feedback_list.append({
                "feedbackId": row[0],
                "learnerId": row[1],
                "nickname": row[2],
                "shortContent": short_content,
                "sendTime": row[4]
            })
        return {"code":1, "data":feedback_list}
    

    @classmethod
    async def get_feedback_detail(cls, feedback_id: int):
        # 管理员：查看单条反馈详情
        sql_str = sql.get_feedback_detail_sql()
        rows = await db.execute_sql(sql_str, (feedback_id,))
        if not rows:
            return {"code": 0, "msg": "反馈不存在"}
        row = rows[0]
        return {
            "code": 1,
            "data": {
                "feedbackId": row[0],
                "learnerId": row[1],
                "nickname": row[2],
                "content": row[3],
                "sendTime": row[4]
            }
        }


    @classmethod
    async def reply_feedback(cls, feedback_id: int, admin_id: int, reply_content: str):
        if not reply_content or len(reply_content) < 2:
            return {"code": 0, "msg": "回复内容不能为空"}

        try:
            sql_insert = sql.insert_reply_sql()
            await db.execute_sql(sql_insert, (feedback_id, admin_id, reply_content))

            sql_update = sql.update_feedback_replied_flag_sql()
            await db.execute_sql(sql_update, (feedback_id,))

            return {"code": 1, "msg": "回复成功"}
        except Exception as e:
            print(e)
            return {"code": 0, "msg": "回复失败"}
        
        












