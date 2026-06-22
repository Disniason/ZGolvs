import pyodbc
import aioodbc

from .config import *
from .sql import sql



"""
class database:

    @classmethod
    def init_db(cls, main_dir : str = "."):

        #print(main_dir)
        db_path = os.path.abspath(os.path.join(main_dir, db_relative_path))
        #print(db_path)
        db_data_path = os.path.join(db_path, db_name + ".mdf")
        db_log_path = os.path.join(db_path, db_name + "_log.ldf")
        print("数据库位置: " + db_data_path)
        
        create_db_sql = sql.generate_create_db_sql(db_name, db_data_path, db_log_path)
        #print(create_db_sql)

        conn_master = pyodbc.connect(
            f"DRIVER={driver};SERVER={server};DATABASE=master;Trusted_Connection=yes",
            autocommit=True
        )
        cursor_master = conn_master.cursor()

        cursor_master.execute(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name='{db_name}') BEGIN {create_db_sql} END")

        cursor_master.close()
        conn_master.close()

        cls.conn = pyodbc.connect(f"DRIVER={driver};SERVER={server};DATABASE={db_name};Trusted_Connection=yes")
        cls.cursor = cls.conn.cursor()
        create_learner_table = sql.generate_create_learner_table_sql()
        cls.cursor.execute(create_learner_table)
        cls.conn.commit()
        cls.conn.close()


    @classmethod
    def get_db(cls):
        return cls.conn
    

    @classmethod
    def connect(cls):
        if not hasattr(database, 'conn'):
            cls.conn = pyodbc.connect(f"DRIVER={driver};SERVER={server};DATABASE={db_name};Trusted_Connection=yes")
        if not hasattr(database, 'cursor'):
            cls.cursor = cls.conn.cursor()


    @classmethod
    def close(cls):
        if hasattr(database, 'cursor'):
            cls.cursor.close()
            del cls.cursor
        if hasattr(database, 'conn'):
            cls.conn.close()
            del cls.conn

"""





class async_database:
    
    @classmethod
    async def init_db(cls, main_dir: str = "."):
        # 原有异步初始化逻辑不变
        db_path = os.path.abspath(os.path.join(main_dir, db_relative_path))
        db_data_path = os.path.join(db_path, db_name + ".mdf")
        db_log_path = os.path.join(db_path, db_name + "_log.ldf")
        print("数据库位置: " + db_data_path)
        
        create_db_sql = sql.generate_create_db_sql(db_name, db_data_path, db_log_path)

        # 异步连接master库
        conn_master = await aioodbc.connect(
            dsn = f"DRIVER={driver};SERVER={server};DATABASE=master;Trusted_Connection=yes",
            autocommit = True
        )
        try:
            cursor_master = await conn_master.cursor()
            await cursor_master.execute(
                f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name='{db_name}') BEGIN {create_db_sql} END"
            )
        finally:
            await conn_master.close()

        # 异步初始化表
        temp_conn = await aioodbc.connect(
            dsn = f"DRIVER={driver};SERVER={server};DATABASE={db_name};Trusted_Connection=yes"
        )
        try:
            temp_cursor = await temp_conn.cursor()
            await temp_cursor.execute(sql.generate_create_learner_table_sql())
            await temp_cursor.execute(sql.generate_create_admin_table_sql())
            await temp_cursor.execute(sql.create_feedback_table_sql())
            await temp_cursor.execute(sql.create_reply_table_sql())
            await temp_cursor.execute(sql.create_vocabulary_table_sql())
            await temp_cursor.execute(sql.create_paper_table_sql())
            await temp_cursor.execute(sql.create_word_book_table_sql())
            await temp_cursor.execute(sql.create_user_exam_answer_table_sql())


            await temp_conn.commit()
        finally:
            await temp_conn.close()


    @classmethod
    async def get_connection(cls):
        # 异步获取数据库连接（每次请求新连接）
        conn = await aioodbc.connect(
            dsn = f"DRIVER={driver};SERVER={server};DATABASE={db_name};Trusted_Connection=yes"
        )
        return conn


    @classmethod
    async def execute_sql(cls, sql: str, params: tuple = None):
        conn = None
        try:
            conn = await cls.get_connection()
            cursor = await conn.cursor()

            # 执行 SQL
            if params:
                await cursor.execute(sql, params)
            else:
                await cursor.execute(sql)

            # --------------------------
            # 核心：区分查询 / 非查询
            # --------------------------
            sql_upper = sql.strip().upper()
            if sql_upper.startswith("SELECT"):
                # 查询 → 返回结果列表
                result = await cursor.fetchall()
                await conn.commit()
                return result
            else:
                # 增删改 → 返回影响行数
                await conn.commit()
                return cursor.rowcount

        except Exception as e:
            if conn:
                await conn.rollback()
            raise e
        finally:
            if conn:
                await conn.close()







