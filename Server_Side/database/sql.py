


class sql:

    @classmethod
    def generate_create_db_sql(cls, db_name, db_data_path, db_log_path):
        return f"""
            CREATE DATABASE {db_name}
            ON PRIMARY(
                NAME = {db_name}_data,
                FILENAME = '{db_data_path}'
            )
            LOG ON(
                NAME = {db_name}_log,
                FILENAME = '{db_log_path}'
            )
        """


    @classmethod
    def generate_create_learner_table_sql(cls):
        return '''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='learner_table' AND xtype='U')
            CREATE TABLE learner_table (
                userId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                userEmail VARCHAR(100) NOT NULL UNIQUE,
                userPassword VARCHAR(60) NOT NULL,
                userName NVARCHAR(50) NOT NULL,
                learnerSex VARCHAR(20) NOT NULL,
                learnerStage VARCHAR(50) NOT NULL,
                learnerExam VARCHAR(100) NOT NULL,
                learnerSchool NVARCHAR(200) NOT NULL,
                createTime DATETIME DEFAULT GETDATE() NOT NULL
            )
        '''
    

    @classmethod
    def generate_create_admin_table_sql(cls):
        return '''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='admin_table' AND xtype='U')
            CREATE TABLE admin_table (
                userId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                userEmail VARCHAR(100) NOT NULL UNIQUE,
                userPassword VARCHAR(60) NOT NULL,
                userName NVARCHAR(50) NOT NULL,
                createTime DATETIME DEFAULT GETDATE() NOT NULL
            )
        '''
    

    @classmethod
    def insert_learner(cls):
        return f"""
            INSERT INTO learner_table (
                userEmail, userPassword, userName, 
                learnerSex, learnerStage, learnerExam, learnerSchool
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
    

    @classmethod
    def insert_admin(cls):
        return f"""
            INSERT INTO admin_table (
                userEmail, userPassword, userName
            ) VALUES (?, ?, ?)
        """
    

    @classmethod
    def query_learner_email(cls):
        return f"""
            SELECT userEmail FROM learner_table 
            WHERE userEmail=? OR (userId=? AND userId IS NOT NULL)
        """
    

    @classmethod
    def query_admin_email(cls):
        return f"""
            SELECT userEmail FROM admin_table 
            WHERE userEmail=? OR (userId=? AND userId IS NOT NULL)
        """
    

    @classmethod
    def check_learner_by_email(cls):
        return "SELECT * FROM learner_table WHERE userEmail=?"
                

    @classmethod
    def check_admin_by_email(cls):
        return "SELECT * FROM admin_table WHERE userEmail=?"
    

    @classmethod
    def learner_login(cls):
        return f"""
            SELECT userId, userEmail, userPassword FROM learner_table
            WHERE userEmail=? OR (userId=? AND userId IS NOT NULL)
        """
    

    @classmethod
    def admin_login(cls):
        return f"""
            SELECT userId, userEmail, userPassword FROM admin_table
            WHERE userEmail=? OR (userId=? AND userId IS NOT NULL)
        """
    

    @classmethod
    def get_learner_info_by_id_sql(cls):
        # 根据用户ID查询完整个人信息
        return f"""
            SELECT 
                userId,
                userEmail,
                userName,
                learnerSex,
                learnerStage,
                learnerExam,
                learnerSchool
            FROM learner_table 
            WHERE userId = ?
        """
    

    @classmethod
    def get_admin_info_by_id_sql(cls):
        return f"""
            SELECT 
                userId,
                userEmail,
                userName
            FROM admin_table 
            WHERE userId = ?
        """


    @classmethod
    def update_learner_field_sql(cls, user_id: int, field: str, value: str):
        # 动态更新用户单个字段（通用方法）
        # 安全校验字段名，防止SQL注入
        allowed_fields = ["userName", "learnerSex", "learnerStage", "learnerExam", "learnerSchool", "userPassword"]
        if field not in allowed_fields:
            raise ValueError("不允许修改的字段")
        return f"""
            UPDATE learner_table 
            SET {field} = ?
            WHERE userId = ?
        """
    

    @classmethod
    def update_admin_field_sql(cls, user_id: int, field: str, value: str):
        # 动态更新用户单个字段（通用方法）
        # 安全校验字段名，防止SQL注入
        allowed_fields = ["userName", "userPassword"]
        if field not in allowed_fields:
            raise ValueError("不允许修改的字段")
        return f"""
            UPDATE admin_table 
            SET {field} = ?
            WHERE userId = ?
        """


    @classmethod
    def delete_learner_sql(cls):
        return f"""
            DELETE FROM learner_table 
            WHERE userId = ?
        """
    

    @classmethod
    def delete_admin_sql(cls):
        return f"""
            DELETE FROM admin_table 
            WHERE userId = ?
        """
    


    







    @classmethod
    def create_feedback_table_sql(cls):
        return f"""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'feedback_table' AND xtype='U')
            CREATE TABLE feedback_table (
                feedbackId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                learnerId INT NOT NULL,
                sendTime DATETIME DEFAULT GETDATE() NOT NULL,
                content NVARCHAR(MAX) NOT NULL,
                replied BIT NOT NULL,
                CONSTRAINT FK_F_L FOREIGN KEY (learnerId) REFERENCES learner_table(userId)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
            )
        """
    

    @classmethod
    def create_reply_table_sql(cls):
        return f"""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'reply_table' AND xtype='U')
            CREATE TABLE reply_table (
                replyId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                feedbackId INT NOT NULL,
                adminId INT NOT NULL,
                sendTime DATETIME DEFAULT GETDATE() NOT NULL,
                content NVARCHAR(MAX) NOT NULL,
                CONSTRAINT FK_R_F FOREIGN KEY (feedbackId) REFERENCES feedback_table(feedbackId)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,
                CONSTRAINT FK_R_A FOREIGN KEY (adminId) REFERENCES admin_table(userId)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,
            )
        """
    

    @classmethod
    def insert_feedback_sql(cls):
        return """
            INSERT INTO feedback_table 
            (learnerId, content, replied)
            VALUES (?, ?, 0)
        """


    @classmethod
    def get_learner_feedbacks_sql(cls):
        return """
            SELECT 
                f.feedbackId, f.learnerId, f.sendTime, f.content, f.replied,
                r.content AS reply_content,
                r.sendTime AS reply_time,
                a.userId AS admin_id
            FROM feedback_table f
            LEFT JOIN reply_table r ON f.feedbackId = r.feedbackId
            LEFT JOIN admin_table a ON r.adminId = a.userId
            WHERE f.learnerId = ?
            ORDER BY f.sendTime DESC
        """
    

    @classmethod
    def get_unreplied_feedbacks_sql(cls):
        # 最早的排在最前面
        return """
            SELECT TOP 8
                f.feedbackId,
                f.learnerId,
                l.userName,
                f.content,
                f.sendTime
            FROM feedback_table f
            JOIN learner_table l ON f.learnerId = l.userId
            WHERE f.replied = 0
            ORDER BY f.sendTime ASC
        """
    

    # 管理员端：回复反馈
    @classmethod
    def insert_reply_sql(cls):
        return """
            INSERT INTO reply_table (feedbackId, adminId, content)
            VALUES (?, ?, ?)
        """


    # 管理员端：更新反馈的 replyId
    @classmethod
    def update_feedback_replied_flag_sql(cls):
        return """
            UPDATE feedback_table
            SET replied = 1
            WHERE feedbackId = ?
        """


    # 管理员端：根据反馈ID查询反馈详情
    @classmethod
    def get_feedback_detail_sql(cls):
        return """
            SELECT 
                f.feedbackId,
                f.learnerId,
                l.userName,
                f.content,
                f.sendTime
            FROM feedback_table f
            JOIN learner_table l ON f.learnerId = l.userId
            WHERE f.feedbackId = ?
        """
    

    @classmethod
    def delete_reply_by_delete_feedback_by_learner_id(cls):
        return "DELETE FROM reply_table WHERE feedbackId IN (SELECT feedbackId FROM feedback_table WHERE learnerId = ?)"


    @classmethod
    def delete_feedback_by_learner_id(cls):
        return "DELETE FROM feedback_table WHERE learnerId = ?"












    
    @classmethod
    def create_word_table_sql(cls, table_name):
        return f"""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = QUOTENAME(?) AND xtype='U')
            CREATE TABLE {table_name} (
                word VARCHAR(50) PRIMARY KEY NOT NULL,
                translations NVARCHAR(400) NOT NULL,
                exchanges NVARCHAR(200) NULL,
                examples NVARCHAR(1000) NULL,
                phonetic NVARCHAR(100) NOT NULL,
                uk_audio_path NVARCHAR(200) NULL,
                us_audio_path NVARCHAR(200) NULL,
                createTime DATETIME DEFAULT GETDATE() NOT NULL
            )
        """


    @classmethod
    def create_vocabulary_table_sql(cls):
        return f"""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'vocabulary_table' AND xtype='U')
            CREATE TABLE vocabulary_table (
                vocabularyId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                vocabularyName NVARCHAR(50) NOT NULL UNIQUE,
                createTime DATETIME DEFAULT GETDATE() NOT NULL
            )
        """
    

    @classmethod
    def insert_vocabulary_sql(cls):
        return f"""
            INSERT INTO vocabulary_table (vocabularyName)
            VALUES (?)
        """
    

    @classmethod
    def create_word_table_insert_vocabulary_sql(cls, table_name):
        return f"""
            BEGIN TRANSACTION;
            BEGIN TRY
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = QUOTENAME(?) AND xtype='U')
                CREATE TABLE {table_name} (
                    word VARCHAR(500) PRIMARY KEY NOT NULL,
                    translations NVARCHAR(MAX) NOT NULL,
                    exchanges NVARCHAR(MAX) NULL,
                    examples NVARCHAR(MAX) NULL,
                    phonetic NVARCHAR(MAX) NOT NULL,
                    uk_audio_path NVARCHAR(MAX) NULL,
                    us_audio_path NVARCHAR(MAX) NULL,
                    createTime DATETIME DEFAULT GETDATE() NOT NULL
                );

                IF NOT EXISTS (SELECT 1 FROM vocabulary_table WHERE vocabularyName = ?)
                INSERT INTO vocabulary_table (vocabularyName) VALUES (?);

                COMMIT TRANSACTION;
            END TRY
            BEGIN CATCH
                ROLLBACK TRANSACTION;
                THROW;
            END CATCH;
        """
    
    
    @classmethod
    def delete_word_table_sql(cls, table_name):
        return f"""
            DELETE FROM vocabulary_table
            WHERE vocabularyName = ?;

            IF OBJECT_ID(N'{table_name}', N'U') IS NOT NULL
            DROP TABLE {table_name};
        """
    

    @classmethod
    def get_all_vocabulary_name_sql(cls):
        return """
            SELECT vocabularyName FROM vocabulary_table ORDER BY createTime DESC;
        """
    

    @classmethod
    def get_all_vocabulary_list_sql(cls):
        return """
            SELECT vocabularyId, vocabularyName, createTime 
            FROM vocabulary_table 
            ORDER BY createTime DESC;
        """
    

    @classmethod
    def check_name_vocabulary_exists_sql(cls):
        return """SELECT COUNT(1) FROM vocabulary_table WHERE vocabularyName = ?"""
    

    @classmethod
    def insert_single_word_sql(cls, table_name):
        return f"""
            INSERT INTO {table_name}
            (word, translations, exchanges, examples, phonetic, uk_audio_path, us_audio_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
    

    @classmethod
    def batch_insert_word_sql(cls, table_name, batch_count: int):
        val_template = "(?, CAST(? AS NVARCHAR(MAX)), CAST(? AS NVARCHAR(MAX)), CAST(? AS NVARCHAR(MAX)), ?, CAST(? AS NVARCHAR(MAX)), CAST(? AS NVARCHAR(MAX)))"
        value_segments = ", ".join([val_template for _ in range(batch_count)])
        return f"""
            INSERT INTO {table_name}
            (word, translations, exchanges, examples, phonetic, uk_audio_path, us_audio_path)
            VALUES {value_segments}
        """
    

    @classmethod
    def get_table_all_spell_sql(cls, table_name):
        return f"""
            SELECT word FROM {table_name} ORDER BY word ASC;
        """


    @classmethod
    def get_single_word_detail_sql(cls, table_name):
        return f"""
            SELECT word,translations,exchanges,examples,phonetic,uk_audio_path,us_audio_path,createTime
            FROM {table_name}
            WHERE word = ?;
        """
    

    @classmethod
    def get_word_table_full_data_sql(cls, table_name):
        return f"""
            SELECT * FROM {table_name} ORDER BY word ASC;
        """


    @classmethod
    def create_word_book_table_sql(cls):
        return f"""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'word_book_table' AND xtype='U')
            CREATE TABLE word_book_table (
                learnerId INT NOT NULL,
                vocabularyId INT NOT NULL,
                learnedWords NVARCHAR(MAX) NULL,
                unlearnedWords NVARCHAR(MAX) NULL,
                learnMode BIT NOT NULL,
                dailyWordNum INT NOT NULL,

                CONSTRAINT PK_word_book_table PRIMARY KEY (learnerId, vocabularyId),

                CONSTRAINT FK_word_book_table_learner
                    FOREIGN KEY (learnerId) REFERENCES learner_table(userId)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,

                CONSTRAINT FK_word_book_table_vocab
                    FOREIGN KEY (vocabularyId) REFERENCES vocabulary_table(vocabularyId)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,
            )
        """
    

    @classmethod
    def check_word_book_exists_sql(cls):
        return """
            SELECT COUNT(1) 
            FROM word_book_table 
            WHERE learnerId = ? AND vocabularyId = ?
        """


    @classmethod
    def insert_word_book_sql(cls):
        return """
            INSERT INTO word_book_table
            (learnerId, vocabularyId, learnedWords, unlearnedWords, learnMode, dailyWordNum)
            VALUES (?, ?, ?, ?, ?, ?)
        """
    

    @classmethod
    def get_user_word_book_list_sql(cls):
        # 联表查询用户单词本全部单词表信息
        return """
            SELECT 
                wb.learnerId,
                wb.vocabularyId,
                wb.learnedWords,
                wb.unlearnedWords,
                wb.learnMode,
                wb.dailyWordNum,
                vt.vocabularyName
            FROM word_book_table wb
            LEFT JOIN vocabulary_table vt ON wb.vocabularyId = vt.vocabularyId
            WHERE wb.learnerId = ?
            ORDER BY vt.vocabularyName ASC
        """
    

    @classmethod
    def get_word_book_config_sql(cls):
        return """
            SELECT learnMode, dailyWordNum
            FROM word_book_table
            WHERE learnerId = ? AND vocabularyId = ?
        """


    @classmethod
    def update_word_book_config_sql(cls):
        return """
            UPDATE word_book_table
            SET learnMode = ?, dailyWordNum = ?
            WHERE learnerId = ? AND vocabularyId = ?
        """
    

    @classmethod
    def get_word_translations_examples_sql(cls, table_name: str):
        return f"""
            SELECT word, translations, examples
            FROM {table_name}
            WHERE word = ?
        """


    @classmethod
    def batch_get_word_translations_sql(cls, table_name: str, word_count: int):
        return f"""
            SELECT TOP {word_count} word, translations
            FROM {table_name}
            ORDER BY NEWID()
        """


    @classmethod
    def update_word_learn_status_sql(cls):
        return """
            UPDATE word_book_table
            SET learnedWords = ?, unlearnedWords = ?
            WHERE learnerId = ? AND vocabularyId = ?
        """


    @classmethod
    def get_vocab_table_name_by_id_sql(cls):
        return """
            SELECT vocabularyName
            FROM vocabulary_table
            WHERE vocabularyId = ?
        """
    

    @classmethod
    def get_full_word_detail_sql(cls, table_name: str):
        return f"""
            SELECT word,translations,exchanges,examples,phonetic,uk_audio_path,us_audio_path
            FROM {table_name}
            WHERE word = ?
        """
    

    @classmethod
    def get_word_book_words_sql(cls, vocab_id: int, learner_id: int):
        return """
            SELECT unlearnedWords, learnedWords
            FROM word_book_table
            WHERE vocabularyId = ? AND learnerId = ?
        """

    @classmethod
    def update_word_book_words_sql(cls, vocab_id: int, learner_id: int, unlearned_str: str, learned_str: str):
        return """
            UPDATE word_book_table
            SET unlearnedWords = ?, learnedWords = ?
            WHERE vocabularyId = ? AND learnerId = ?
        """
    

    @classmethod
    def move_word_back_to_unlearned_sql(cls, vocab_id: int, learner_id: int, new_un: str, new_learn: str):
        return """
            UPDATE word_book_table
            SET unlearnedWords = ?, learnedWords = ?
            WHERE vocabularyId = ? AND learnerId = ?
        """
    

    @classmethod
    def get_single_book_analyze_sql(cls):
        return """
            SELECT 
                vocabularyId,
                learnedWords,
                unlearnedWords,
                learnMode,
                dailyWordNum
            FROM word_book_table
            WHERE learnerId = ? AND vocabularyId = ?
        """


    @classmethod
    def get_all_user_book_list_sql(cls):
        return """
            SELECT 
                w.vocabularyId,
                v.vocabularyName,
                w.learnedWords,
                w.unlearnedWords,
                w.learnMode,
                w.dailyWordNum
            FROM word_book_table w
            LEFT JOIN vocabulary_table v ON w.vocabularyId = v.vocabularyId
            WHERE w.learnerId = ?
        """


    @classmethod
    def get_book_daily_target_sql(cls):
        return """
            SELECT dailyWordNum, unlearnedWords FROM word_book_table
            WHERE learnerId = ? AND vocabularyId = ?
        """
    

    @classmethod
    def get_learner_all_wordbook_sql(cls):
        return """
            SELECT wb.vocabularyId, vt.vocabularyName
            FROM word_book_table wb
            LEFT JOIN vocabulary_table vt ON wb.vocabularyId = vt.vocabularyId
            WHERE wb.learnerId = ?
            ORDER BY vt.vocabularyName ASC;
        """


    @classmethod
    def unbind_wordbook_sql(cls):
        return """
            DELETE FROM word_book_table
            WHERE learnerId = ? AND vocabularyId = ?;
        """








    @classmethod
    def create_paper_sql(cls, table_name):
        return f"""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = QUOTENAME(?) AND xtype='U')
            CREATE TABLE [{table_name}] (
                questionId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                question NVARCHAR(MAX) NOT NULL,
                answer NVARCHAR(MAX) NOT NULL,
                objective BIT NOT NULL,
                score REAL NOT NULL,
                totalScore REAL NOT NULL
            )
        """
    

    @classmethod
    def create_paper_table_sql(cls):
        return f"""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'paper_table' AND xtype='U')
            CREATE TABLE paper_table (
                paperId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                paperName NVARCHAR(50) NOT NULL UNIQUE,
                createTime DATETIME DEFAULT GETDATE() NOT NULL
            )
        """
    

    @classmethod
    def insert_paper_sql(cls):
        return f"""
            INSERT INTO paper_table (paperName)
            VALUES (?)
        """
    

    @classmethod
    def create_paper_insert_paper_sql(cls, table_name):
        return f"""
            BEGIN TRANSACTION;
            BEGIN TRY
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = QUOTENAME(?) AND xtype='U')
                CREATE TABLE [{table_name}] (
                    questionId INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
                    question NVARCHAR(MAX) NOT NULL,
                    answer NVARCHAR(MAX) NOT NULL,
                    objective BIT NOT NULL,
                    score REAL NOT NULL,
                    totalScore REAL NOT NULL
                );

                IF NOT EXISTS (SELECT 1 FROM paper_table WHERE paperName = ?)
                INSERT INTO paper_table (paperName) VALUES (?);

                COMMIT TRANSACTION;
            END TRY
            BEGIN CATCH
                ROLLBACK TRANSACTION;
                THROW;
            END CATCH;
        """


    @classmethod
    def delete_paper_sql(cls, table_name):
        return f"""
            DELETE FROM paper_table
            WHERE paperName = ?;

            IF OBJECT_ID(N'{table_name}', N'U') IS NOT NULL
            DROP TABLE [{table_name}];
        """
    

    @classmethod
    def check_name_paper_exists_sql(cls):
        return """SELECT COUNT(1) FROM paper_table WHERE paperName = ?"""


    @classmethod
    def get_all_paper_list_sql(cls):
        return """
            SELECT paperId, paperName, createTime 
            FROM paper_table 
            ORDER BY createTime DESC;
        """


    @classmethod
    def insert_single_question_sql(cls, table_name):
        return f"""
            INSERT INTO [{table_name}] (question, answer, objective, score, totalScore)
            VALUES (?, ?, ?, ?, ?)
        """


    @classmethod
    def batch_insert_question_sql(cls, table_name, batch_count: int):
        val_template = "(CAST(? AS NVARCHAR(MAX)), CAST(? AS NVARCHAR(MAX)), ?, ?, ?)"
        value_segments = ", ".join([val_template for _ in range(batch_count)])
        return f"""
            INSERT INTO [{table_name}] (question, answer, objective, score, totalScore)
            VALUES {value_segments}
        """


    @classmethod
    def check_name_paper_exists_sql(cls):
        return """SELECT COUNT(1) FROM paper_table WHERE paperName = ?"""


    @classmethod
    def get_paper_all_questions_sql(cls, table_name):
        return f"""
            SELECT questionId, question, answer, objective 
            FROM [{table_name}] 
            ORDER BY questionId ASC;
        """


    @classmethod
    def get_single_question_detail_sql(cls, table_name):
        return f"""
            SELECT questionId, question, answer, objective 
            FROM [{table_name}] 
            WHERE questionId = ?;
        """


    @classmethod
    def delete_single_question_sql(cls, table_name):
        return f"""
            DELETE FROM [{table_name}] 
            WHERE questionId = ?;
        """


    @classmethod
    def update_question_sql(cls, table_name):
        return f"""
            UPDATE [{table_name}]
            SET question = ?, answer = ?, objective = ?
            WHERE questionId = ?;
        """
    

    @classmethod
    def get_paper_all_question_id_list_sql(cls, table_name: str):
        # 获取试卷全部题目ID列表
        return f"""
            SELECT questionId FROM [{table_name}] ORDER BY questionId ASC;
        """


    @classmethod
    def get_single_exam_question_sql(cls, table_name: str):
        # 获取单道题目完整详情（题干、答案、题型）
        return f"""
            SELECT questionId, question, answer, objective
            FROM [{table_name}]
            WHERE questionId = ?;
        """


    @classmethod
    def batch_save_user_exam_answer_sql(cls):
        # 批量保存用户本次考试作答记录
        return """
            INSERT INTO user_exam_answer_table
            (learnerId, paperName, questionId, userAnswer, createTime)
            VALUES (?, ?, ?, ?, GETDATE())
        """
    

    @classmethod
    def get_question_all_info_sql(cls, paper_name):
        return f"SELECT questionId, question, answer, objective, score, totalScore FROM [{paper_name}] ORDER BY questionId ASC"
    






    @classmethod
    def create_user_exam_answer_table_sql(cls):
        return """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'user_exam_answer_table' AND xtype='U')
            CREATE TABLE user_exam_answer_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                learnerId INT NOT NULL,
                paperName NVARCHAR(50) NOT NULL,
                questionId INT NOT NULL,
                userAnswer NVARCHAR(MAX) NULL,
                createTime DATETIME DEFAULT GETDATE() NOT NULL,

                CONSTRAINT FK_exam_learner FOREIGN KEY (learnerId) REFERENCES learner_table(userId) ON DELETE CASCADE
            )
        """









