"""ORM model registry.

Importing this package registers every mapped class on ``Base.metadata``.
``app.db.session.init_db()`` relies on that side effect so ``create_all`` can see
all tables even when the caller never imported an API router that happens to
pull the models in. Keep the imports below (and ``__all__``) in sync with the
model modules under ``app/models/``.
"""

from app.models.catalog import CourseCatalog, CourseCatalogMaterial, CourseOffering
from app.models.code_problem import CodeProblem, CodeProblemTestCase
from app.models.conversation import Conversation, Message
from app.models.course import Course, CourseEnrollment
from app.models.others import (
    AgentLog,
    AsyncTask,
    CourseKnowledgeGraph,
    Evaluation,
    LearningActivity,
    LearningPath,
    OperationLog,
    Resource,
    UserPersonalizedResource,
    UserProfile,
)
from app.models.personalized_resource_generation import PersonalizedResourceGeneration
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import RegistrationCode, User


__all__ = [
    "AgentLog",
    "AsyncTask",
    "CodeProblem",
    "CodeProblemTestCase",
    "Conversation",
    "Course",
    "CourseCatalog",
    "CourseCatalogMaterial",
    "CourseEnrollment",
    "CourseKnowledgeGraph",
    "CourseOffering",
    "Evaluation",
    "LearningActivity",
    "LearningPath",
    "Message",
    "OperationLog",
    "PersonalizedResourceGeneration",
    "QuizAnswer",
    "QuizQuestion",
    "QuizSession",
    "RegistrationCode",
    "Resource",
    "User",
    "UserPersonalizedResource",
    "UserProfile",
]
