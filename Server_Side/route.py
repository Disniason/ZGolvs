import os
import random
import uvicorn
import secrets
import urllib.parse
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, Body, File, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import FastAPI, HTTPException, APIRouter, Request, UploadFile, status

from paper import paper
from request_class import *
from user import learner, admin
from paper_exam import paper_exam
from vocabulary import vocabulary
from message import feedback_reply
from word_question import word_question
from database.db import async_database as db
from word_book import word_book, word_book_analyze
from constant import main_dir, templates_path, get_admin_route, num_workers


oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "api/login", auto_error = False)
router = APIRouter()
templates = Jinja2Templates(directory = templates_path)


# 新增：令牌验证中间件（验证接口访问权限）
async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=401, detail="未提供令牌")
    verify_result = await learner.verify_token(token)
    if verify_result["code"] != 1:
        raise HTTPException(status_code=401, detail=verify_result["msg"])
    return verify_result["data"]


# 页面路由
@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})



# 业务接口路由
@router.post("/api/send-code")
async def send_code_api(data: EmailRequest):
    return await learner.send_code(data.email)


@router.post("/api/verify-code")
async def verify_code_api(data: CodeRequest):
    return await learner.verify_code(data.email, data.code)


@router.post("/api/finish-register")
async def finish_register_api(data: RegisterRequest):
    return await learner.finish_register(data.email, data.encrypted_password)


@router.post("/api/login-send-code")
async def login_send_code(data: dict):
    return await learner.send_login_code(data["account"])


@router.post("/api/login")
async def login_api(data: dict):
    return await learner.login(
        account=data["account"],
        loginType=data["loginType"],
        password=data.get("password"),
        code=data.get("code")
    )


@router.post("/api/logout")
async def logout_api(token: str = Depends(oauth2_scheme)):
    if not token:
        return JSONResponse({"code": 0, "msg": "未登录"}, status_code=401)
    verify_result = await learner.verify_token(token)
    if verify_result["code"] != 1:
        return JSONResponse({"code": 0, "msg": verify_result["msg"]}, status_code=401)
    user_id = verify_result["data"]["sub"]
    return await learner.logout(user_id)


@router.get("/api/verify-token")
async def verify_token_api(token: str = Depends(oauth2_scheme)):
    if not token:
        return JSONResponse({"code": 0, "msg": "未提供令牌"})
    return await learner.verify_token(token)


# 依赖项：解析JWT令牌，获取用户ID
async def get_current_learner_id(request: Request) -> int:
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ")[1]
    #print(token)

    try:
        # 关键修复：必须传 token_type="access"
        payload = await learner.verify_token(token, token_type="access")

        # 必须是成功格式
        if payload.get("code") != 1:
            print("code != 1")
            print(payload)
            raise HTTPException(status_code=401, detail=payload.get("msg", "令牌无效"))

        # 从 data 中取出 sub（用户ID）
        user_id = payload["data"].get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="令牌无效")

        return int(user_id)

    except Exception as e:
        print("令牌解析异常:", e)
        raise HTTPException(status_code=401, detail="令牌无效")
    """

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ")[1]

    # 调用验证
    res = await learner.verify_token(token, "access")
    
    if res["code"] != 1:
        print("验证失败原因：", res["msg"])
        raise HTTPException(status_code=401, detail=res["msg"])

    return int(res["data"]["sub"])


@router.get(f"/api/learner/profile")
async def get_learner_profile(user_id: int = Depends(get_current_learner_id)):
    result = await learner.get_learner_info(user_id)
    if result["code"] != 1:
        raise HTTPException(status_code=400, detail=result["msg"])
    return result


@router.post(f"/api/learner/update")
async def update_learner_profile(
    data: LearnerUpdateRequest,
    user_id: int = Depends(get_current_learner_id)
):
    # 过滤掉None值，只保留需要修改的字段
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="没有修改任何信息")

    result = await learner.update_learner_info(user_id, update_data)
    if result["code"] != 1:
        raise HTTPException(status_code=400, detail=result["msg"])
    return result


@router.post(f"/api/learner/delete")
async def delete_learner_account(user_id: int = Depends(get_current_learner_id)):
    result = await learner.delete_learner(user_id)
    if result["code"] != 1:
        raise HTTPException(status_code=400, detail=result["msg"])
    return result


# 用户提交反馈
@router.post("/api/learner/feedback/submit")
async def api_learner_add_feedback(
    data: FeedbackSubmitModel,
    token: str = Depends(get_current_learner_id)
):
    learner_id = token
    return await feedback_reply.add_feedback(learner_id, data.content)


# 用户查看自己的反馈记录
@router.get("/api/learner/feedback/list")
async def api_learner_my_feedbacks(
    learner_id: int = Depends(get_current_learner_id)
):
    return await feedback_reply.get_my_feedbacks(learner_id)


@router.get(f"/api/learner/word-table/list")
async def get_vocab_list():
    res = await vocabulary.get_all_vocabulary_tables()
    return {"code": 1, "list": res, "msg": "搜索成功"}


@router.get("/api/learner/word-table/search")
async def search_vocab_list(keyword: str = ""):
    res = await vocabulary.search_vocabulary_tables(keyword)
    return {"code": 1, "list": res, "msg": "搜索成功"}


@router.post("/api/learner/word-table/add-to-book")
async def add_to_word_book(
    body: AddWordBookBody = Body(...),
    learner_id: int = Depends(get_current_learner_id)
):
    res = await word_book.add_vocabulary_to_book(learner_id, body.vocabularyId, body.vocabularyName)
    # 不抛HTTPException，统一返回{code,msg}，前端正常解析
    return res


@router.get("/api/learner/word-book/list")
async def get_my_word_books(
    learner_id: int = Depends(get_current_learner_id)
):
    result = await word_book.get_user_all_word_books(learner_id)
    return result


@router.get("/api/learner/word-book/config")
async def get_book_config(
    vocabularyId: int,
    learner_id: int = Depends(get_current_learner_id)
):
    res = await word_book.get_word_book_config(learner_id, vocabularyId)
    return res


@router.post("/api/learner/word-book/config/update")
async def update_book_config(
    body: UpdateConfigBody = Body(...),
    learner_id: int = Depends(get_current_learner_id)
):
    res = await word_book.update_word_book_config(
        learner_id,
        body.vocabularyId,
        body.learnMode,
        body.dailyWordNum
    )
    return res


@router.get("/api/learner/word-question/get-audio-stream")
async def get_audio_stream(file_path: str):
    if not os.path.exists(file_path):
        return {"code":0, "msg":"音频文件不存在"}
    def stream_audio():
        with open(file_path, "rb") as f:
            while chunk := f.read(1024*4):
                yield chunk
    return StreamingResponse(stream_audio(), media_type="audio/mpeg")


@router.get("/api/learner/word-question/check-daily-finish")
async def check_daily_finish(
    vocabularyId: int = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.check_daily_finish(learner_id, vocabularyId)


@router.get("/api/learner/word-question/get-word-pool")
async def get_word_pool(
    vocabularyId: int = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.get_valid_daily_word_pool(learner_id, vocabularyId)


@router.get("/api/learner/word-question/single-sentence-question")
async def gen_sentence_q(
    vocabularyId: int = Query(...),
    targetWord: str = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.generate_sentence_choose_word_question(learner_id, vocabularyId, targetWord)


@router.get("/api/learner/word-question/single-meaning-question")
async def gen_meaning_q(
    vocabularyId: int = Query(...),
    targetWord: str = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.generate_meaning_choose_word_question(learner_id, vocabularyId, targetWord)


@router.get("/api/learner/word-question/single-audio-question")
async def gen_audio_q(
    vocabularyId: int = Query(...),
    targetWord: str = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.generate_audio_choose_word_question(learner_id, vocabularyId, targetWord)


@router.get("/api/learner/word-question/single-spell-meaning-question")
async def gen_spell_q(
    vocabularyId: int = Query(...),
    targetWord: str = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.generate_spell_choose_meaning_question(learner_id, vocabularyId, targetWord)


@router.post("/api/learner/word-question/submit-answer")
async def submit_answer(
    body: AnswerSubmitBody,
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.check_single_answer(
        learner_id,
        body.vocabularyId,
        body.targetWord,
        body.userSelectIndex,
        body.realCorrectIndex
    )


@router.post("/api/learner/word-question/finish-daily")
async def finish_daily(
    body: FinishDailyBody,
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.finish_daily_all_correct(learner_id, body.vocabularyId)


@router.get("/api/learner/word-question/get-audio-stream")
async def get_audio_stream(file_path: str = Query(...)):
    if not os.path.exists(file_path):
        return {"code":0, "msg":"音频文件不存在"}
    def stream_audio():
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                yield chunk
    return StreamingResponse(stream_audio(), media_type="audio/mpeg")


@router.get("/api/learner/seq/get-word-book")
async def get_seq_word_book(
    vocabularyId: int = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.get_word_book_words(learner_id, vocabularyId)


@router.get("/api/learner/seq/generate-question")
async def gen_seq_question(
    vocabularyId: int = Query(...),
    targetWord: str = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    type_list = ["sentence","meaning","audio","spell"]
    pick_type = random.choice(type_list)
    if pick_type == "sentence":
        return await word_question.gen_seq_sentence_q(learner_id, vocabularyId, targetWord)
    elif pick_type == "meaning":
        return await word_question.gen_seq_meaning_q(learner_id, vocabularyId, targetWord)
    elif pick_type == "audio":
        return await word_question.gen_seq_audio_q(learner_id, vocabularyId, targetWord)
    elif pick_type == "spell":
        return await word_question.gen_seq_spell_q(learner_id, vocabularyId, targetWord)


@router.post("/api/learner/seq/submit-answer")
async def seq_submit_answer(
    body: SeqAnswerBody,
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.check_seq_answer(
        learner_id, body.vocabularyId, body.targetWord, body.userSelectIndex, body.realCorrectIndex
    )


@router.post("/api/learner/seq/move-word-learned")
async def seq_move_word(
    body: MoveWordBody,
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.move_word_to_learned(learner_id, body.vocabularyId, body.targetWord)


"""
@router.get("/api/learner/word-question/get-audio-stream")
async def get_audio_stream(file_path: str = Query(...)):
    import os
    if not os.path.exists(file_path):
        return {"code":0, "msg":"音频不存在"}
    def stream():
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                yield chunk
    from fastapi.responses import StreamingResponse
    return StreamingResponse(stream(), media_type="audio/mpeg")
"""


@router.get("/api/learner/test/get-word-book")
async def get_test_word_book(
    vocabularyId: int = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.get_word_book_words(learner_id, vocabularyId)


@router.get("/api/learner/test/generate-question")
async def gen_test_question(
    vocabularyId: int = Query(...),
    targetWord: str = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    type_list = ["sentence","meaning","audio","spell"]
    pick_type = random.choice(type_list)
    if pick_type == "sentence":
        return await word_question.gen_test_sentence_q(learner_id, vocabularyId, targetWord)
    elif pick_type == "meaning":
        return await word_question.gen_test_meaning_q(learner_id, vocabularyId, targetWord)
    elif pick_type == "audio":
        return await word_question.gen_test_audio_q(learner_id, vocabularyId, targetWord)
    elif pick_type == "spell":
        return await word_question.gen_test_spell_q(learner_id, vocabularyId, targetWord)


@router.post("/api/learner/test/submit-answer")
async def test_submit_answer(
    body: TestAnswerBody,
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.check_test_answer(
        learner_id, body.vocabularyId, body.targetWord, body.userSelectIndex, body.realCorrectIndex
    )


@router.post("/api/learner/test/move-word-back")
async def test_move_word_back(
    body: MoveBackWordBody,
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_question.move_word_back_unlearned(learner_id, body.vocabularyId, body.targetWord)


@router.get("/api/learner/analyze/single-book")
async def analyze_single_book(
    vocabularyId: int = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_book_analyze.get_single_book_data(learner_id, vocabularyId)


@router.get("/api/learner/analyze/all-books-compare")
async def analyze_all_books(
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_book_analyze.get_all_user_books_compare(learner_id)


@router.get("/api/learner/analyze/daily-predict")
async def analyze_daily_predict(
    vocabularyId: int = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_book_analyze.get_daily_predict_info(learner_id, vocabularyId)


@router.get("/api/learner/wordbook/list")
async def get_user_wordbook(learner_id: int = Depends(get_current_learner_id)):
    return await word_book.get_learner_wordbook_list(learner_id)


@router.post("/api/learner/wordbook/unbind")
async def unbind_wordbook(
    body: UnbindWordBookBody = Body(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await word_book.unbind_vocabulary(learner_id, body.vocabularyId)


@router.get("/api/learner/paper/get-all-paper")
async def get_all_paper():
    res = await paper.get_all_paper_tables()
    return res


@router.get("/api/learner/paper/get-all-questions")
async def get_all_question_id(paperName: str = Query(...), learner_id: int = Depends(get_current_learner_id)):
    return await paper_exam.get_paper_all_qid(paperName)


@router.get("/api/learner/paper/get-single-question")
async def get_single_question(
    table_name: str = Query(...),
    question_id: int = Query(...),
    learner_id: int = Depends(get_current_learner_id)
):
    return await paper_exam.get_single_question_detail(table_name, question_id)


@router.post("/api/learner/paper/submit-all")
async def submit_exam_all_answer(
    body: ExamSubmitBody = Body(...),
    learner_id: int = Depends(get_current_learner_id)
):
    # 1. 先保存用户作答记录（保留原入库逻辑）
    await paper_exam.batch_submit_exam_answer(learner_id, body.paperName, body.answerList)
    # 2. 执行自动批改，返回批改结果给前端
    judge_result = await paper_exam.judge_paper_all_answers(body.paperName, body.answerList)
    return judge_result














admin_route = get_admin_route()


@router.get(f"/{admin_route}", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "admin_route": admin_route
    })


@router.get(f"/{admin_route}/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("admin_register.html", {
        "request": request,
        "admin_route": admin_route
    })


@router.get(f"/{admin_route}/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "admin_route": admin_route
    })


@router.get(f"/{admin_route}/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("admin_home.html", {
        "request": request,
        "admin_route": admin_route
    })





@router.post(f"/api/{admin_route}/send-code")
async def send_code_api(data: EmailRequest):
    return await admin.send_code(data.email)


@router.post(f"/api/{admin_route}/verify-code")
async def verify_code_api(data: CodeRequest):
    return await admin.verify_code(data.email, data.code)


@router.post(f"/api/{admin_route}/finish-register")
async def finish_register_api(data: RegisterRequest):
    return await admin.finish_register(data.email, data.encrypted_password)


@router.post(f"/api/{admin_route}/login-send-code")
async def login_send_code(data: dict):
    return await admin.send_login_code(data["account"])


@router.post(f"/api/{admin_route}/login")
async def login_api(data: dict):
    return await admin.login(
        account=data["account"],
        loginType=data["loginType"],
        password=data.get("password"),
        code=data.get("code")
    )


@router.post(f"/api/{admin_route}/logout")
async def logout_api(token: str = Depends(oauth2_scheme)):
    if not token:
        return JSONResponse({"code": 0, "msg": "未登录"}, status_code=401)
    verify_result = await admin.verify_token(token)
    if verify_result["code"] != 1:
        return JSONResponse({"code": 0, "msg": verify_result["msg"]}, status_code=401)
    user_id = verify_result["data"]["sub"]
    return await admin.logout(user_id)


@router.get(f"/api/{admin_route}/verify-token")
async def verify_token_api(token: str = Depends(oauth2_scheme)):
    if not token:
        return JSONResponse({"code": 0, "msg": "未提供令牌"})
    return await admin.verify_token(token)


async def get_current_admin_id(request: Request) -> int:

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ")[1]

    # 调用验证
    res = await admin.verify_token(token, "access")
    
    if res["code"] != 1:
        print("验证失败原因：", res["msg"])
        raise HTTPException(status_code=401, detail=res["msg"])

    return int(res["data"]["sub"])


@router.get(f"/api/{admin_route}/profile")
async def get_admin_profile(user_id: int = Depends(get_current_admin_id)):
    result = await admin.get_admin_info(user_id)
    if result["code"] != 1:
        raise HTTPException(status_code=400, detail=result["msg"])
    return result


@router.post(f"/api/{admin_route}/update")
async def update_admin_profile(
    data: LearnerUpdateRequest,
    user_id: int = Depends(get_current_admin_id)
):
    # 过滤掉None值，只保留需要修改的字段
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="没有修改任何信息")

    result = await admin.update_admin_info(user_id, update_data)
    if result["code"] != 1:
        raise HTTPException(status_code=400, detail=result["msg"])
    return result


@router.post(f"/api/{admin_route}/delete")
async def delete_admin_account(user_id: int = Depends(get_current_admin_id)):
    result = await admin.delete_admin(user_id)
    if result["code"] != 1:
        raise HTTPException(status_code=400, detail=result["msg"])
    return result


# 查询用户信息
@router.get(f"/api/{admin_route}/learner/info")
async def admin_get_learner_info(user_id: int):
    return await admin.get_learner_info(user_id)


# 编辑用户信息
@router.post(f"/api/{admin_route}/learner/update")
async def admin_update_learner(data: AdminUpdateLearnerModel):
    update_data = {
        "nickname": data.nickname,
        "gender": data.gender,
        "stage": data.stage,
        "exam": data.exam,
        "school": data.school
    }
    return await admin.update_learner_info(data.user_id, update_data)


# 注销用户
@router.post(f"/api/{admin_route}/learner/delete")
async def admin_delete_learner(user_id: int):
    return await admin.delete_learner(user_id)








@router.get(f"/api/{admin_route}/word-table/list")
async def get_vocab_list():
    res = await vocabulary.get_all_vocabulary_tables()
    # 适配前端只取name数组，兼容原有js渲染逻辑
    if res["code"] == 1:
        simple_list = [item["vocabularyName"] for item in res["data"]]
        return {"code": 1, "msg": "查询成功", "list": simple_list}
    return res


@router.post(f"/api/{admin_route}/word-table/create")
async def create_vocab_table(body: TableNameBody = Body(...)):
    result = await vocabulary.add_vocabulary_table(body.table_name)
    return result

# 3. 删除单词表 POST
@router.post(f"/api/{admin_route}/word-table/delete")
async def delete_vocab_table(body: TableNameBody = Body(...)):
    result = await vocabulary.delete_vocabulary_table(body.table_name)
    return result


@router.post(f"/api/{admin_route}/word-table/json-import")
async def json_import_word(
    table_name: str = Form(...),
    json_file: UploadFile = File(...)
):
    # 读取文件二进制
    file_bytes = await json_file.read()
    # 调用业务导入函数
    result = await vocabulary.import_word_from_json(table_name, file_bytes)
    return result


@router.post(f"/api/{admin_route}/word-table/spell-list")
async def get_spell_list(body: TableNameBody = Body(...)):
    res = await vocabulary.get_table_word_spell_list(body.table_name)
    return res


@router.post(f"/api/{admin_route}/word-table/word-detail")
async def get_word_detail(body: WordDetailBody = Body(...)):
    res = await vocabulary.get_single_word_info(body.table_name, body.word)
    return res


@router.post(f"/api/{admin_route}/word-table/play-audio")
async def play_word_audio(body: WordAudioBody = Body(...)):
    # 1.调用业务类校验文件
    res_check = await vocabulary.get_audio_file_path(body.table_name, body.word, body.audio_type)
    if res_check["code"] != 1:
        return res_check
    
    file_path = res_check["file_path"]

    # 2.定义文件生成器，流式分片读取返回
    def audio_stream_generator():
        chunk_size = 1024 * 64  # 64KB分片
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    # 3.返回流式mp3音频
    return StreamingResponse(
        audio_stream_generator(),
        media_type="audio/mpeg",
        status_code=status.HTTP_200_OK
    )


@router.post(f"/api/{admin_route}/word-table/export-all")
async def export_word_table_all(body: TableNameBody = Body(...)):
    try:
        export_res = await vocabulary.export_table_to_excel(body.table_name)
        if export_res["code"] != 1:
            return export_res

        excel_buffer = export_res["excel_bytes"]
        table_name = body.table_name
        # 1. 基础备用文件名：纯英文数字（latin1安全无中文）
        safe_ascii_filename = f"{table_name}_word_export.xlsx"
        # 2. 带中文完整文件名，url编码后给filename*
        full_cn_filename = f"{table_name}_单词表全量数据.xlsx"
        import urllib.parse
        encoded_cn_name = urllib.parse.quote(full_cn_filename, encoding="utf-8")

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                # 旧兼容：纯ASCII安全文件名
                "Content-Disposition": f'attachment; filename="{safe_ascii_filename}"; filename*=utf-8\'\'{encoded_cn_name}'
            }
        )
    except Exception as e:
        print("导出全局异常：", repr(e))
        return {"code":0, "msg":f"服务生成Excel失败：{str(e)}"}










@router.post("/api/{admin_route}/paper/create-paper")
async def add_paper(body: PaperNameBody = Body(...)):
    res = await paper.add_paper_table(body.paperName)
    return res


@router.get("/api/{admin_route}/paper/get-all-paper")
async def get_all_paper():
    res = await paper.get_all_paper_tables()
    return res


@router.post("/api/{admin_route}/paper/delete-paper")
async def delete_paper(body: PaperNameBody = Body(...)):
    res = await paper.delete_paper_table(body.paperName)
    return res


@router.post("/api/{admin_route}/paper/upload-question-json")
async def import_questions(
    paperName: str = Form(...),
    jsonFile: UploadFile = File(...)
):
    file_bytes = await jsonFile.read()
    res = await paper.import_questions_from_json(paperName, file_bytes)
    return res


@router.get("/api/{admin_route}/paper/get-all-questions")
async def get_paper_questions(paperName: str = Query(...)):
    res = await paper.get_paper_all_questions(paperName)
    return res


@router.get("/api/{admin_route}/paper/export-all-question")
async def export_paper(paperName: str = Query(...)):
    res = await paper.export_paper_to_excel(paperName)
    if res["code"] != 1:
        return res
    # 中文文件名URL编码，解决latin1编码报错
    safe_filename = urllib.parse.quote(res["filename"])
    return StreamingResponse(
        res["excel_bytes"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{safe_filename}"
        }
    )


@router.post("/api/{admin_route}/paper/get-single-question")
async def get_single_question(body: PaperQuestionBody = Body(...)):
    res = await paper.get_single_question_info(body.table_name, body.question_id)
    return res


@router.post("/api/{admin_route}/paper/delete-question")
async def delete_question(body: PaperQuestionBody = Body(...)):
    res = await paper.delete_single_question(body.table_name, body.question_id)
    return res


@router.put("/api/{admin_route}/paper/update-question")
async def update_question(body: UpdateQuestionBody = Body(...)):
    res = await paper.update_question(
        body.table_name,
        body.question_id,
        body.question,
        body.answer,
        body.objective
    )
    return res


@router.get("/api/{admin_route}/paper/search-paper")
async def search_paper(keyword: str = Query(default="")):
    res = await paper.search_paper_tables(keyword)
    return res








@router.post(f"/api/{admin_route}/paper/create")
async def api_create_word_table(data: CreatePaperModel):
    return await admin.create_paper(data.table_name)


@router.post(f"/api/{admin_route}/paper/delete")
async def delete_word_table(data: DeletePaperModel):
    return await admin.delete_paper(data.table_name)


# 管理员：获取所有未回复反馈
@router.get(f"/api/{admin_route}/feedback/unreplied")
async def admin_get_unreplied_feedbacks(
    admin_id: int = Depends(get_current_admin_id)
):
    return await feedback_reply.get_unreplied_feedbacks()


# 管理员：获取单条反馈详情
@router.get(f"/api/{admin_route}/feedback/detail/{{feedback_id}}")
async def admin_get_feedback_detail(
    feedback_id: int,
    admin_id: int = Depends(get_current_admin_id)
):
    return await feedback_reply.get_feedback_detail(feedback_id)


# 管理员：提交回复
@router.post(f"/api/{admin_route}/feedback/reply")
async def admin_reply_feedback(
    data: ReplySubmitModel,
    admin_id: int = Depends(get_current_admin_id)
):
    return await feedback_reply.reply_feedback(data.feedbackId, admin_id, data.content)















# 应用初始化
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db(main_dir)
    
    yield  # 应用运行中
    
    # 关闭时执行的逻辑（原 shutdown 事件，这里可以留空）
    pass


# 初始化 FastAPI 时指定 lifespan
app = FastAPI(
    title = "在线背单词网站",
    lifespan = lifespan
)

app.include_router(router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 允许所有来源
    allow_credentials=True,     # 允许 Cookie
    allow_methods=["*"],        # 允许所有方法（GET/POST/OPTIONS 等）
    allow_headers=["*"],        # 允许所有请求头（包含 Token）
)


def main_route():
    print(f"管理员路由: {admin_route}")
    # 启动UVicorn（建议使用workers多进程）
    #uvicorn.run("route:app", host="0.0.0.0", port=5000, workers = num_workers)
    uvicorn.run("route:app", host="0.0.0.0", port=5000, workers = 1)
    


