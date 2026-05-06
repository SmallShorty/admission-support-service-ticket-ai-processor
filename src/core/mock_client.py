import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

MOCK_BASE_URL = "http://[::1]:3001"
TIMEOUT = 5.0

FALLBACK_APPLICANT = {
    "id": "00000000-0000-0000-0000-000000000000",
    "personalInfo": {
        "firstName": "Алексей",
        "lastName": "Демидов",
        "patronymic": "Сергеевич",
        "email": "demo@university.ru",
        "phone": "+7 (999) 000-00-00",
    },
    "snils": "000-000-000 00",
    "quotas": {
        "hasBvi": False,
        "hasSpecialQuota": False,
        "hasSeparateQuota": False,
        "hasTargetQuota": False,
        "hasPriorityRight": False,
    },
    "documents": {
        "originalDocumentReceived": False,
        "originalDocumentReceivedAt": None,
    },
    "examScores": [
        {"subjectName": "Русский язык", "score": 78, "type": "ege"},
        {"subjectName": "Математика", "score": 72, "type": "ege"},
        {"subjectName": "Информатика", "score": 81, "type": "ege"},
    ],
    "selectedPrograms": [
        {
            "programId": 1,
            "programCode": "09.03.01",
            "programName": "Информатика и вычислительная техника",
            "studyForm": "full-time",
            "admissionType": "budget",
            "priority": 1,
        }
    ],
    "createdAt": "2026-05-06T09:00:00.000Z",
    "_is_fallback": True,
}


async def get_applicant_by_snils(snils: str) -> dict:
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=TIMEOUT, http2=False, proxy=None) as client:
            try:
                response = await client.post(
                    f"{MOCK_BASE_URL}/mock/applicant",
                    json={"snils": snils},
                )
                response.raise_for_status()
                return response.json()
            except (httpx.ReadError, httpx.ConnectError) as e:
                logger.warning(f"attempt {attempt+1}: {type(e).__name__}, retrying...")
                await asyncio.sleep(0.5)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 502 and attempt < 2:
                    await asyncio.sleep(0.5)
                    continue
                logger.warning(f"mock-service returned {e.response.status_code}, using fallback")
                return FALLBACK_APPLICANT
            except Exception as e:
                logger.warning(f"mock-service unreachable: {type(e).__name__}: {e}, using fallback")
                return FALLBACK_APPLICANT
    return FALLBACK_APPLICANT
