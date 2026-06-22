from typing import List
from pydantic import BaseModel




class EmailRequest(BaseModel):
    email: str


class CodeRequest(BaseModel):
    email: str
    code: str


class RegisterRequest(BaseModel):
    email: str
    encrypted_password: str


class LearnerUpdateRequest(BaseModel):
    nickname: str | None = None
    gender: str | None = None
    stage: str | None = None
    exam: str | None = None
    school: str | None = None
    password: str | None = None


class FeedbackSubmitModel(BaseModel):
    content: str


class ReplySubmitModel(BaseModel):
    feedbackId: int
    content: str


class CreateWordTableModel(BaseModel):
    table_name: str


class DeleteWordTableModel(BaseModel):
    table_name: str


class CreatePaperModel(BaseModel):
    table_name: str


class DeletePaperModel(BaseModel):
    table_name: str


class AdminUpdateLearnerModel(BaseModel):
    user_id: int
    nickname: str = None
    gender: str = None
    stage: str = None
    exam: str = None
    school: str = None


class TableNameBody(BaseModel):
    table_name: str


class TableNameBody(BaseModel):
    table_name: str


class WordDetailBody(BaseModel):
    table_name: str
    word: str


class WordAudioBody(BaseModel):
    table_name: str
    word: str
    audio_type: str  # uk / us

"""
class AddWordBookBody(BaseModel):
    learnerId: int
    vocabularyId: int
    vocabularyName: str
"""


class AddWordBookBody(BaseModel):
    vocabularyId: int
    vocabularyName: str


class UpdateConfigBody(BaseModel):
    vocabularyId: int
    learnMode: int
    dailyWordNum: int


class AnswerSubmitBody(BaseModel):
    vocabularyId: int
    targetWord: str
    userSelectIndex: int
    realCorrectIndex: int


class FinishDailyBody(BaseModel):
    vocabularyId: int


class MoveWordBody(BaseModel):
    vocabularyId: int
    targetWord: str


class SeqAnswerBody(BaseModel):
    vocabularyId: int
    targetWord: str
    userSelectIndex: int
    realCorrectIndex: int


class TestAnswerBody(BaseModel):
    vocabularyId: int
    targetWord: str
    userSelectIndex: int
    realCorrectIndex: int


class MoveBackWordBody(BaseModel):
    vocabularyId: int
    targetWord: str


class UnbindWordBookBody(BaseModel):
    vocabularyId: int


class PaperNameBody(BaseModel):
    paperName: str


class PaperQuestionBody(BaseModel):
    table_name: str
    question_id: int


class UpdateQuestionBody(BaseModel):
    table_name: str
    question_id: int
    question: str
    answer: str
    objective: bool


class SingleAnswerItem(BaseModel):
    questionId: int
    userAnswer: str


class ExamSubmitBody(BaseModel):
    paperName: str
    answerList: List[SingleAnswerItem]



