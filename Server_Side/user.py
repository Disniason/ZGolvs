import jwt
import bcrypt
import pyodbc
import random
import asyncio
import smtplib
import secrets
from redis.asyncio import from_url
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

from database.sql import sql
from database.db import async_database as db
from constant import LEARNER_REDIS_URL, ADMIN_REDIS_URL, email_config


class user:

    defaultId = "null"
    defaultPassword = "null"
    defaultEmail = "2731700768@qq.com"
    defaultName = "unnamed"

    def __init__(self, id, password, email, name):
        self.userId = id
        self.userPassword = password
        self.userEmail = email
        self.userName = name

    def __eq__(self, other):
        if not isinstance(other, user):
            return False
        return self.userId == other.userId

    def __hash__(self):
        return hash(self.userId)

    def getDict(self):
        return {
            "userId": self.userId,
            "userPassword": self.userPassword,
            "userEmail": self.userEmail,
            "userName": self.userName
        }



class learner(user):

    sexs = ("男", "女")
    stages = {"小学", "初中", "高中", "本科", "专科", "硕士研究生", "博士研究生", "其它"}
    exams = {"高考", "cet4", "cet6", "其它"}

    defaultSex = "未知"
    defaultStage = "未知"
    defaultExam = "未知"
    defaultSchool = ""

    # 邮件配置
    EMAIL_HOST = email_config["EMAIL_HOST"]
    EMAIL_PORT = email_config["EMAIL_PORT"]
    EMAIL_USER = email_config["EMAIL_USER"]
    EMAIL_PWD = email_config["EMAIL_PWD"]

    JWT_SECRET_KEY = secrets.token_hex(32)
    #JWT_SECRET_KEY = "test12345678"
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 120
    REFRESH_TOKEN_EXPIRE_DAYS = 7

    redis_client = from_url(LEARNER_REDIS_URL)


    def __init__(self, learner_dict: dict = dict()):
        super().__init__(
            learner_dict.get("userId", self.defaultId),
            learner_dict.get("userPassword", self.defaultPassword),
            learner_dict.get("userEmail", self.defaultEmail),
            learner_dict.get("userName", self.defaultName)
        )
        self.learnerSex = learner_dict.get("learnerSex") in self.sexs and learner_dict["learnerSex"] or self.defaultSex
        self.learnerStage = learner_dict.get("learnerStage", self.defaultStage)
        self.learnerExam = learner_dict.get("learnerExam", self.defaultExam)
        self.learnerSchool = learner_dict.get("learnerSchool", self.defaultSchool)


    def getDict(self):
        learner_dict = super().getDict()
        learner_dict.update({
            "learnerSex": self.learnerSex,
            "learnerStage": self.learnerStage,
            "learnerExam": self.learnerExam,
            "learnerSchool": self.learnerSchool
        })
        return learner_dict
    

    # 生成JWT令牌
    @classmethod
    def create_access_token(cls, data: dict, expires_delta: timedelta = None):
        to_encode = data.copy()
        # 设置过期时间
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire, "type": "access"})
        # 生成令牌
        encoded_jwt = jwt.encode(to_encode, cls.JWT_SECRET_KEY, algorithm=cls.JWT_ALGORITHM)
        return encoded_jwt
    

    # 生成刷新令牌
    @classmethod
    def create_refresh_token(cls, data: dict):
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, cls.JWT_SECRET_KEY, algorithm=cls.JWT_ALGORITHM)
        # 刷新令牌存入Redis（用于注销）
        asyncio.create_task(cls.redis_client.setex(
            f"refresh_token:{data['sub']}",
            cls.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            encoded_jwt
        ))
        return encoded_jwt
    

    # 验证令牌有效性
    @classmethod
    async def verify_token(cls, token: str, token_type: str = "access"):
        """
        try:
            # 解码令牌
            payload = jwt.decode(token, cls.JWT_SECRET_KEY, algorithms=[cls.JWT_ALGORITHM])
            print(payload)
            # 验证令牌类型
            if payload.get("type") != token_type:
                return {"code": 0, "msg": "令牌类型错误"}
            # 验证用户是否存在（可选）
            user_id = payload.get("sub")
            if not user_id:
                print(payload)
                return {"code": 0, "msg": "令牌无效"}
            print(user_id)
            # 检查刷新令牌是否已注销（仅验证refresh token时）
            if token_type == "refresh":
                stored_token = await cls.redis_client.get(f"refresh_token:{user_id}")
                if not stored_token or stored_token.decode() != token:
                    return {"code": 0, "msg": "令牌已注销"}
            return {"code": 1, "msg": "令牌有效", "data": payload}
        except jwt.ExpiredSignatureError:
            return {"code": 0, "msg": "令牌已过期"}
        except jwt.InvalidTokenError:
            print("解码令牌出现异常")
            return {"code": 0, "msg": "令牌无效"}
        """

        try:
            # 修复：增加 options，解决版本不兼容导致的解码失败
            payload = jwt.decode(
                token, 
                cls.JWT_SECRET_KEY, 
                algorithms=[cls.JWT_ALGORITHM],
                options={"verify_exp": True}  # 明确开启过期校验
            )

            #print("解析成功的 payload:", payload)

            if payload.get("type") != token_type:
                return {"code": 0, "msg": "令牌类型错误"}
            
            user_id = payload.get("sub")
            if not user_id:
                return {"code": 0, "msg": "令牌无效"}
            
            if token_type == "refresh":
                stored_token = await cls.redis_client.get(f"refresh_token:{user_id}")
                if not stored_token or stored_token.decode() != token:
                    return {"code": 0, "msg": "令牌已注销"}
            
            return {"code": 1, "msg": "令牌有效", "data": payload}
        
        except jwt.ExpiredSignatureError:
            return {"code": 0, "msg": "令牌已过期"}
        except Exception as e:
            print("JWT 解码真实错误：", str(e))  # 打印真实错误
            return {"code": 0, "msg": "令牌无效"}


    @classmethod
    async def send_code(cls, email: str):
        # 发送注册验证码（异步+Redis限流）
        # 1. 限流检查（60秒内只能发送一次）
        rate_key = f"rate_limit:{email}"
        if await cls.redis_client.exists(rate_key):
            return {"code": 0, "msg": "1分钟内只能发送一次验证码", "type": "rate_limit"}

        # 2. 检查邮箱是否已注册
        result = await db.execute_sql(sql.check_learner_by_email(), (email,))
        if result:
            return {"code": 0, "msg": "邮箱已被注册", "type": "exists"}

        # 3. 生成验证码并存储（10分钟过期）
        code = f"{random.randint(100000, 999999)}"
        code_key = f"verify_code:{email}"
        await cls.redis_client.setex(code_key, 600, code)  # 10分钟过期

        # 4. 设置限流标记（60秒过期）
        await cls.redis_client.setex(rate_key, 60, "1")

        # 5. 异步发送邮件（非阻塞）
        asyncio.create_task(cls.send_mail_task(email, code))

        return {"code": 1, "msg": "验证码已发送", "type": "sent"}


    @classmethod
    async def send_mail_task(cls, to_email, code):
        # 异步发送邮件
        try:
            msg = MIMEText(f"验证码：{code}，10分钟内有效", "plain", "utf-8")
            msg["From"] = cls.EMAIL_USER
            msg["To"] = to_email
            msg["Subject"] = "注册验证码"
            
            # 同步SMTP改为异步（或使用aiosmtplib）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, cls._send_mail_sync, to_email, msg)
        except Exception as e:
            print(f"邮件发送失败: {e}")


    @classmethod
    def _send_mail_sync(cls, to_email, msg):
        # 同步邮件发送（用线程池执行，不阻塞事件循环）
        with smtplib.SMTP_SSL(cls.EMAIL_HOST, cls.EMAIL_PORT) as smtp:
            smtp.login(cls.EMAIL_USER, cls.EMAIL_PWD)
            smtp.sendmail(cls.EMAIL_USER, [to_email], msg.as_string())


    @classmethod
    async def verify_code(cls, email: str, code: str):
        # 验证验证码（异步+Redis）
        code_key = f"verify_code:{email}"
        stored_code = await cls.redis_client.get(code_key)
        
        if not stored_code:
            return {"code": 0, "msg": "验证码不存在或已过期", "type": "expired"}
        if stored_code.decode() != code:
            return {"code": 0, "msg": "验证码错误", "type": "wrong"}
        
        # 验证通过后删除验证码
        await cls.redis_client.delete(code_key)
        return {"code": 1, "msg": "验证通过，请设置密码", "type": "ok"}


    @classmethod
    async def finish_register(cls, email: str, password: str):
        # 完成注册（异步数据库操作）
        # 二次检查邮箱是否已注册
        check_sql = sql.check_learner_by_email()
        if await db.execute_sql(check_sql, (email,)):
            return {"code": 0, "msg": "邮箱已被注册", "type": "exists"}

        try:
            # 密码加密
            salt = bcrypt.gensalt()
            hashed_pw = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            # 异步插入数据
            insert_sql = sql.insert_learner()
            username = "用户" + email[:email.find("@")]
            await db.execute_sql(insert_sql, (
                email, hashed_pw, username,
                cls.defaultSex, cls.defaultStage, cls.defaultExam, cls.defaultSchool
            ))
            
            return {"code": 1, "msg": "注册成功，请登录", "type": "success"}
        except Exception as e:
            print(f"注册失败: {e}")
            return {"code": 0, "msg": "注册失败"}


    @classmethod
    async def send_login_code(cls, account: str):
        # 发送登录验证码
        # 查询用户邮箱
        temp_sql = sql.query_learner_email()
        result = await db.execute_sql(temp_sql, (account, account if account.isdigit() else -1))
        
        if not result:
            return {"code": 0, "msg": "账号不存在"}
        
        email = result[0][0]
        # 复用注册验证码逻辑
        code = f"{random.randint(100000, 999999)}"
        code_key = f"verify_code:{email}"
        await cls.redis_client.setex(code_key, 600, code)  # 10分钟过期

        # 4. 设置限流标记（60秒过期）
        rate_key = f"rate_limit:{email}"
        if await cls.redis_client.exists(rate_key):
            return {"code": 0, "msg": "1分钟内只能发送一次验证码", "type": "rate_limit"}
        await cls.redis_client.setex(rate_key, 60, "1")

        # 5. 异步发送邮件（非阻塞）
        asyncio.create_task(cls.send_mail_task(email, code))

        return {"code": 1, "msg": "验证码已发送", "type": "sent"}


    @classmethod
    async def login(cls, account: str, loginType: str, password=None, code=None):
        # 查询用户信息
        login_sql = sql.learner_login()
        result = await db.execute_sql(login_sql, (account, account if account.isdigit() else -1))
        
        if not result:
            return {"code": 0, "msg": "账号不存在"}
        
        userId, email, pwd_in_db = result[0]

        if loginType == "password":
            # 密码登录
            if not bcrypt.checkpw(password.encode('utf-8'), pwd_in_db.encode('utf-8')):
                return {"code": 0, "msg": "密码错误"}
        else:
            # 验证码登录
            code_key = f"verify_code:{email}"
            stored_code = await cls.redis_client.get(code_key)
            if not stored_code or stored_code.decode() != code:
                return {"code": 0, "msg": "验证码错误或已过期"}
            # 验证通过后删除验证码
            await cls.redis_client.delete(code_key)

        # 生成访问令牌和刷新令牌
        access_token_expires = timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = cls.create_access_token(
            data={"sub": str(userId), "email": email},
            expires_delta=access_token_expires
        )
        refresh_token = cls.create_refresh_token(data={"sub": str(userId)})

        return {
            "code": 1, 
            "msg": "登录成功", 
            "data": {
                "userId": userId, 
                "email": email,
                "access_token": access_token,  # 访问令牌（前端存在localStorage/cookie）
                "refresh_token": refresh_token,  # 刷新令牌（可选）
                "token_type": "bearer"  # 令牌类型
            }
        }
    

    @classmethod
    async def logout(cls, user_id: str):
        # 删除Redis中的刷新令牌
        await cls.redis_client.delete(f"refresh_token:{user_id}")
        # 可选：将access token加入黑名单（需Redis）
        return {"code": 1, "msg": "退出登录成功"}
    

    @classmethod
    async def get_learner_info(cls, user_id: int):
        # 获取学习用户个人信息
        try:
            rows = await db.execute_sql(sql.get_learner_info_by_id_sql(), (user_id,))

            if not rows:
                return {"code": 0, "msg": "用户不存在"}

            row = rows[0]
            return {
                "code": 1,
                "data": {
                    "userId": row[0],
                    "userEmail": row[1],
                    "nickname": row[2],
                    "gender": row[3],
                    "stage": row[4],
                    "exam": row[5],
                    "school": row[6]
                }
            }
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return {"code": 0, "msg": "服务器错误"}


    @classmethod
    async def update_learner_info(cls, user_id: int, update_data: dict):
        """
        修改个人信息（支持单字段修改）
        """
        try:
            # 前端字段 → 数据库字段映射
            field_map = {
                "nickname": "userName",
                "gender": "learnerSex",
                "stage": "learnerStage",
                "exam": "learnerExam",
                "school": "learnerSchool",
                "password": "userPassword"
            }

            for key, value in update_data.items():
                db_field = field_map.get(key)
                if not db_field:
                    continue

                # 密码加密
                if key == "password":
                    salt = bcrypt.gensalt()
                    value = bcrypt.hashpw(value.encode(), salt).decode()

                update_sql = sql.update_learner_field_sql(user_id, db_field, value)
                
                await db.execute_sql(update_sql, (value, user_id))

            return {"code": 1, "msg": "修改成功"}

        except ValueError as e:
            return {"code": 0, "msg": str(e)}
        except Exception as e:
            print(f"修改用户信息失败: {e}")
            return {"code": 0, "msg": "修改失败，请重试"}


    @classmethod
    async def delete_learner(cls, user_id: int):
        # 注销账号（删除用户）
        try:
            
            await db.execute_sql(sql.delete_reply_by_delete_feedback_by_learner_id(), (user_id,))
            await db.execute_sql(sql.delete_feedback_by_learner_id(), (user_id,))
            row_count = await db.execute_sql(sql.delete_learner_sql(), (user_id,))

            if row_count == 0:
                return {"code": 0, "msg": "用户不存在或已注销"}

            return {"code": 1, "msg": "账号注销成功"}

        except Exception as e:
            print(f"注销用户失败: {e}")
            return {"code": 0, "msg": "注销失败，请重试"}
















class admin(user):

    def __init__(self, learner_dict: dict = dict()):
        super().__init__(
            learner_dict.get("userId", self.defaultId),
            learner_dict.get("userPassword", self.defaultPassword),
            learner_dict.get("userEmail", self.defaultEmail),
            learner_dict.get("userName", self.defaultName)
        )
        self.learnerSex = learner_dict.get("learnerSex") in self.sexs and learner_dict["learnerSex"] or self.defaultSex
        self.learnerStage = learner_dict.get("learnerStage", self.defaultStage)
        self.learnerExam = learner_dict.get("learnerExam", self.defaultExam)
        self.learnerSchool = learner_dict.get("learnerSchool", self.defaultSchool)


    def getDict(self):
        learner_dict = super().getDict()
        learner_dict.update({
            "learnerSex": self.learnerSex,
            "learnerStage": self.learnerStage,
            "learnerExam": self.learnerExam,
            "learnerSchool": self.learnerSchool
        })
        return learner_dict
    

    # 邮件配置
    EMAIL_HOST = email_config["EMAIL_HOST"]
    EMAIL_PORT = email_config["EMAIL_PORT"]
    EMAIL_USER = email_config["EMAIL_USER"]
    EMAIL_PWD = email_config["EMAIL_PWD"]

    JWT_SECRET_KEY = secrets.token_hex(32)
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 120
    REFRESH_TOKEN_EXPIRE_DAYS = 7

    
    redis_client = from_url(ADMIN_REDIS_URL)
    

    # 生成JWT令牌
    @classmethod
    def create_access_token(cls, data: dict, expires_delta: timedelta = None):
        to_encode = data.copy()
        # 设置过期时间
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire, "type": "access"})
        # 生成令牌
        encoded_jwt = jwt.encode(to_encode, cls.JWT_SECRET_KEY, algorithm=cls.JWT_ALGORITHM)
        return encoded_jwt
    

    # 生成刷新令牌
    @classmethod
    def create_refresh_token(cls, data: dict):
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, cls.JWT_SECRET_KEY, algorithm=cls.JWT_ALGORITHM)
        # 刷新令牌存入Redis（用于注销）
        asyncio.create_task(cls.redis_client.setex(
            f"refresh_token:{data['sub']}",
            cls.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            encoded_jwt
        ))
        return encoded_jwt
    

    # 验证令牌有效性
    @classmethod
    async def verify_token(cls, token: str, token_type: str = "access"):
        try:
            # 修复：增加 options，解决版本不兼容导致的解码失败
            payload = jwt.decode(
                token, 
                cls.JWT_SECRET_KEY, 
                algorithms=[cls.JWT_ALGORITHM],
                options={"verify_exp": True}  # 明确开启过期校验
            )

            #print("解析成功的 payload:", payload)

            if payload.get("type") != token_type:
                return {"code": 0, "msg": "令牌类型错误"}
            
            user_id = payload.get("sub")
            if not user_id:
                return {"code": 0, "msg": "令牌无效"}
            
            if token_type == "refresh":
                stored_token = await cls.redis_client.get(f"refresh_token:{user_id}")
                if not stored_token or stored_token.decode() != token:
                    return {"code": 0, "msg": "令牌已注销"}
            
            return {"code": 1, "msg": "令牌有效", "data": payload}
        
        except jwt.ExpiredSignatureError:
            return {"code": 0, "msg": "令牌已过期"}
        except Exception as e:
            print("JWT 解码真实错误：", str(e))  # 打印真实错误
            return {"code": 0, "msg": "令牌无效"}


    @classmethod
    async def send_code(cls, email: str):
        # 发送注册验证码（异步+Redis限流）
        # 1. 限流检查（60秒内只能发送一次）
        rate_key = f"rate_limit:{email}"
        if await cls.redis_client.exists(rate_key):
            return {"code": 0, "msg": "1分钟内只能发送一次验证码", "type": "rate_limit"}

        # 2. 检查邮箱是否已注册
        result = await db.execute_sql(sql.check_admin_by_email(), (email,))
        if result:
            return {"code": 0, "msg": "邮箱已被注册", "type": "exists"}

        # 3. 生成验证码并存储（10分钟过期）
        code = f"{random.randint(100000, 999999)}"
        code_key = f"verify_code:{email}"
        await cls.redis_client.setex(code_key, 600, code)  # 10分钟过期

        # 4. 设置限流标记（60秒过期）
        await cls.redis_client.setex(rate_key, 60, "1")

        # 5. 异步发送邮件（非阻塞）
        asyncio.create_task(cls.send_mail_task(email, code))

        return {"code": 1, "msg": "验证码已发送", "type": "sent"}


    @classmethod
    async def send_mail_task(cls, to_email, code):
        # 异步发送邮件
        try:
            msg = MIMEText(f"验证码：{code}，10分钟内有效", "plain", "utf-8")
            msg["From"] = cls.EMAIL_USER
            msg["To"] = to_email
            msg["Subject"] = "注册验证码"
            
            # 同步SMTP改为异步（或使用aiosmtplib）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, cls._send_mail_sync, to_email, msg)
        except Exception as e:
            print(f"邮件发送失败: {e}")


    @classmethod
    def _send_mail_sync(cls, to_email, msg):
        # 同步邮件发送（用线程池执行，不阻塞事件循环）
        with smtplib.SMTP_SSL(cls.EMAIL_HOST, cls.EMAIL_PORT) as smtp:
            smtp.login(cls.EMAIL_USER, cls.EMAIL_PWD)
            smtp.sendmail(cls.EMAIL_USER, [to_email], msg.as_string())


    @classmethod
    async def verify_code(cls, email: str, code: str):
        # 验证验证码（异步+Redis）
        code_key = f"verify_code:{email}"
        stored_code = await cls.redis_client.get(code_key)
        
        if not stored_code:
            return {"code": 0, "msg": "验证码不存在或已过期", "type": "expired"}
        if stored_code.decode() != code:
            return {"code": 0, "msg": "验证码错误", "type": "wrong"}
        
        # 验证通过后删除验证码
        await cls.redis_client.delete(code_key)
        return {"code": 1, "msg": "验证通过，请设置密码", "type": "ok"}


    @classmethod
    async def finish_register(cls, email: str, password: str):
        # 完成注册（异步数据库操作）
        # 二次检查邮箱是否已注册
        check_sql = sql.check_admin_by_email()
        if await db.execute_sql(check_sql, (email,)):
            return {"code": 0, "msg": "邮箱已被注册", "type": "exists"}

        try:
            # 密码加密
            salt = bcrypt.gensalt()
            hashed_pw = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            # 异步插入数据
            insert_sql = sql.insert_admin()
            username = "用户" + email[:email.find("@")]
            await db.execute_sql(insert_sql, (
                email, hashed_pw, username
            ))
            
            return {"code": 1, "msg": "注册成功，请登录", "type": "success"}
        except Exception as e:
            print(f"注册失败: {e}")
            return {"code": 0, "msg": "注册失败"}


    @classmethod
    async def send_login_code(cls, account: str):
        # 发送登录验证码
        # 查询用户邮箱
        temp_sql = sql.query_learner_email()
        result = await db.execute_sql(temp_sql, (account, account if account.isdigit() else -1))
        
        if not result:
            return {"code": 0, "msg": "账号不存在"}
        
        email = result[0][0]
        # 复用注册验证码逻辑
        code = f"{random.randint(100000, 999999)}"
        code_key = f"verify_code:{email}"
        await cls.redis_client.setex(code_key, 600, code)  # 10分钟过期

        # 4. 设置限流标记（60秒过期）
        rate_key = f"rate_limit:{email}"
        if await cls.redis_client.exists(rate_key):
            return {"code": 0, "msg": "1分钟内只能发送一次验证码", "type": "rate_limit"}
        await cls.redis_client.setex(rate_key, 60, "1")

        # 5. 异步发送邮件（非阻塞）
        asyncio.create_task(cls.send_mail_task(email, code))

        return {"code": 1, "msg": "验证码已发送", "type": "sent"}


    @classmethod
    async def login(cls, account: str, loginType: str, password=None, code=None):
        # 查询用户信息
        login_sql = sql.admin_login()
        result = await db.execute_sql(login_sql, (account, account if account.isdigit() else -1))
        
        if not result:
            return {"code": 0, "msg": "账号不存在"}
        
        userId, email, pwd_in_db = result[0]

        if loginType == "password":
            # 密码登录
            if not bcrypt.checkpw(password.encode('utf-8'), pwd_in_db.encode('utf-8')):
                return {"code": 0, "msg": "密码错误"}
        else:
            # 验证码登录
            code_key = f"verify_code:{email}"
            stored_code = await cls.redis_client.get(code_key)
            if not stored_code or stored_code.decode() != code:
                return {"code": 0, "msg": "验证码错误或已过期"}
            # 验证通过后删除验证码
            await cls.redis_client.delete(code_key)

        # 生成访问令牌和刷新令牌
        access_token_expires = timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = cls.create_access_token(
            data={"sub": str(userId), "email": email},
            expires_delta=access_token_expires
        )
        refresh_token = cls.create_refresh_token(data={"sub": str(userId)})

        return {
            "code": 1, 
            "msg": "登录成功", 
            "data": {
                "userId": userId, 
                "email": email,
                "access_token": access_token,  # 访问令牌（前端存在localStorage/cookie）
                "refresh_token": refresh_token,  # 刷新令牌（可选）
                "token_type": "bearer"  # 令牌类型
            }
        }
    

    @classmethod
    async def logout(cls, user_id: str):
        # 删除Redis中的刷新令牌
        await cls.redis_client.delete(f"refresh_token:{user_id}")
        # 可选：将access token加入黑名单（需Redis）
        return {"code": 1, "msg": "退出登录成功"}
    

    @classmethod
    async def get_admin_info(cls, user_id: int):
        # 获取学习用户个人信息
        try:
            rows = await db.execute_sql(sql.get_admin_info_by_id_sql(), (user_id,))

            if not rows:
                return {"code": 0, "msg": "用户不存在"}

            row = rows[0]
            return {
                "code": 1,
                "data": {
                    "userId": row[0],
                    "userEmail": row[1],
                    "nickname": row[2],
                }
            }
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return {"code": 0, "msg": "服务器错误"}


    @classmethod
    async def update_admin_info(cls, user_id: int, update_data: dict):
        """
        修改个人信息（支持单字段修改）
        """
        try:
            # 前端字段 → 数据库字段映射
            field_map = {
                "nickname": "userName",
                "password": "userPassword"
            }

            for key, value in update_data.items():
                db_field = field_map.get(key)
                if not db_field:
                    continue

                # 密码加密
                if key == "password":
                    salt = bcrypt.gensalt()
                    value = bcrypt.hashpw(value.encode(), salt).decode()

                update_sql = sql.update_admin_field_sql(user_id, db_field, value)
                
                await db.execute_sql(update_sql, (value, user_id))

            return {"code": 1, "msg": "修改成功"}

        except ValueError as e:
            return {"code": 0, "msg": str(e)}
        except Exception as e:
            print(f"修改用户信息失败: {e}")
            return {"code": 0, "msg": "修改失败，请重试"}


    @classmethod
    async def delete_admin(cls, user_id: int):
        # 注销账号（删除用户）
        try:
            
            delete_sql = sql.delete_admin_sql()
            
            row_count = await db.execute_sql(delete_sql, (user_id,))

            if row_count == 0:
                return {"code": 0, "msg": "用户不存在或已注销"}

            return {"code": 1, "msg": "账号注销成功"}

        except Exception as e:
            print(f"注销用户失败: {e}")
            return {"code": 0, "msg": "注销失败，请重试"}
        






    @classmethod
    async def get_learner_info(cls, user_id: int):
        # 获取学习用户个人信息
        try:
            rows = await db.execute_sql(sql.get_learner_info_by_id_sql(), (user_id,))

            if not rows:
                return {"code": 0, "msg": "用户不存在"}

            row = rows[0]
            return {
                "code": 1,
                "data": {
                    "userId": row[0],
                    "userEmail": row[1],
                    "nickname": row[2],
                    "gender": row[3],
                    "stage": row[4],
                    "exam": row[5],
                    "school": row[6]
                }
            }
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return {"code": 0, "msg": "服务器错误"}


    @classmethod
    async def update_learner_info(cls, user_id: int, update_data: dict):
        """
        修改个人信息（支持单字段修改）
        """
        try:
            # 前端字段 → 数据库字段映射
            field_map = {
                "nickname": "userName",
                "gender": "learnerSex",
                "stage": "learnerStage",
                "exam": "learnerExam",
                "school": "learnerSchool"
            }

            for key, value in update_data.items():
                db_field = field_map.get(key)
                if not db_field:
                    continue

                update_sql = sql.update_learner_field_sql(user_id, db_field, value)
                
                await db.execute_sql(update_sql, (value, user_id))

            return {"code": 1, "msg": "修改成功"}

        except ValueError as e:
            return {"code": 0, "msg": str(e)}
        except Exception as e:
            print(f"修改用户信息失败: {e}")
            return {"code": 0, "msg": "修改失败，请重试"}


    @classmethod
    async def delete_learner(cls, user_id: int):
        # 注销账号（删除用户）
        try:

            await db.execute_sql(sql.delete_reply_by_delete_feedback_by_learner_id(), (user_id,))
            await db.execute_sql(sql.delete_feedback_by_learner_id(), (user_id,))
            row_count = await db.execute_sql(sql.delete_learner_sql(), (user_id,))

            if row_count == 0:
                return {"code": 0, "msg": "用户不存在或已注销"}

            return {"code": 1, "msg": "账号注销成功"}

        except Exception as e:
            print(f"注销用户失败: {e}")
            return {"code": 0, "msg": "注销失败，请重试"}











    @classmethod
    async def create_word_table(cls, table_name):
        """
        create_sql = sql.create_word_table_sql(table_name)
        insert_sql = sql.insert_vocabulary_sql()

        try:
            # 打开连接
            conn = await db.get_connection()
            cursor = await conn.cursor()

            # 第一步：创建单词表
            await cursor.execute(create_sql, (table_name,))

            # 第二步：自动插入词汇表记录（关键！）
            await cursor.execute(insert_sql, (table_name,))

            # 提交事务
            await conn.commit()
            return {"code": 1, "msg": f"单词表「{table_name}」创建成功"}

        except Exception as e:
            if conn is not None:
                try:
                    await conn.rollback()
                except:
                    pass
            return {"code": 0, "msg": "新建单词表失败，请重试"}
        """
        try:
            await db.execute_sql(
                sql.create_word_table_insert_vocabulary_sql(table_name),
                (table_name, table_name)
            )
            return {"code": 1, "msg": f"单词表「{table_name}」创建成功"}

        except Exception as e:
            print("创建单词表失败：", e)
            return {"code": 0, "msg": "创建单词表失败，请重试"}

        
    @classmethod
    async def delete_word_table(cls, table_name: str):
        try:
            # 执行删除
            await db.execute_sql(
                sql.delete_word_table_sql(table_name),
                (table_name,)
            )
            return {"code": 1, "msg": "单词表已彻底删除"}

        except Exception as e:
            print("删除单词表失败：", e)
            return {"code": 0, "msg": "删除失败，可能不存在或已被删除"}
        

    @classmethod
    async def create_paper(cls, table_name):
        try:
            await db.execute_sql(
                sql.create_paper_insert_paper_sql(table_name),
                (table_name, table_name)
            )
            return {"code": 1, "msg": f"试卷「{table_name}」创建成功"}

        except Exception as e:
            print("创建试卷失败：", e)
            return {"code": 0, "msg": "创建试卷失败，请重试"}

        
    @classmethod
    async def delete_paper(cls, table_name: str):
        try:
            await db.execute_sql(
                sql.delete_paper_sql(table_name),
                (table_name,)
            )
            return {"code": 1, "msg": "试卷已彻底删除"}

        except Exception as e:
            print("删除试卷失败：", e)
            return {"code": 0, "msg": "删除失败，可能不存在或已被删除"}








