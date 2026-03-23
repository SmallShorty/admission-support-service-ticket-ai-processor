# 📘 Документация Ticket Classifier Model

Данный микросервис является частью экосистемы **Admission Support Service**. Его основная задача — автоматическая классификация входящих тикетов от абитуриентов с использованием NLP-модели.

---

## 🏷 Категории обращений

Все категории и их смысловые описания для нейросети хранятся в файле:
`src/core/categories.json`

### Текущий список ID (Slugs):

- `tech_issue` — Технические сбои.
- `deadlines` — Сроки подачи.
- `docs_submission` — Процесс подачи документов.
- `status_check` — Проверка списков и статуса.
- `admission_scores` — Баллы и шансы.
- `finance_contracts` — Оплата и договора.
- `enrollment` — Зачисление и приказы.
- `dormitory` — Общежитие.
- `academic_info` — Учеба и расписание.
- `events` — Мероприятия и ДОД.
- `general_info` — Общая информация.
- `program_consult` — Консультация по направлениям.

---

## 🛠 Технологический стек

- **Framework:** FastAPI
- **Server:** Uvicorn (ASGI)
- **ML Engine:** Hugging Face Transformers
- **Model:** `facebook/bart-large-mnli` (Zero-Shot)

## 🚀 Как расширить систему

Чтобы добавить новую категорию:

1. Откройте `src/core/categories.json`.
2. Добавьте новую пару `"ID": "Description"`.
3. Перезапустите сервис. Нейросеть автоматически начнет учитывать новую категорию благодаря подходу Zero-Shot.
