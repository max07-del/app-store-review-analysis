# Сценарій відеодемонстрації

Орієнтовна тривалість: 4–6 хвилин.

## 1. Вступ

«Привіт! Це тестове завдання — REST API для збору й аналізу відгуків з Apple
App Store. Рішення написане на Python і FastAPI та повністю запускається
локально».

## 2. Архітектура

Коротко показати структуру папок і пояснити:

- `apple_client.py` перевіряє застосунок і отримує review JSON;
- `review_collector.py` керує пагінацією, дедуплікацією та випадковою вибіркою;
- `text_analysis.py` виконує очищення, sentiment і пошук проблем;
- `repository.py` зберігає результат у SQLite;
- API повертає JSON/CSV та візуальний HTML-звіт.

## 3. Запуск

У терміналі виконати:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Відкрити `http://127.0.0.1:8000/docs`.

## 4. Створення аналізу

У Swagger відкрити `POST /api/v1/analyses` і передати:

```json
{
  "app": "1459969523",
  "country": "us",
  "count": 100,
  "seed": 42
}
```

Показати отриманий `analysis_id`, середній рейтинг, rating distribution,
sentiment distribution, негативні ключові слова та рекомендації.

## 5. Перегляд і завантаження

Показати:

- `GET /api/v1/analyses/{id}`;
- `GET /api/v1/analyses/{id}/reviews`;
- CSV download endpoint;
- `/api/v1/analyses/{id}/report` у браузері.

## 6. Обробка помилок

Передати неправильне значення `app`, наприклад `instagram`, і показати
структуровану помилку `INVALID_APP_IDENTIFIER`.

## 7. Завершення

«API працює локально, має тести, Swagger-документацію, SQLite-збереження,
експорт даних і готовий звіт. Для production я б виніс збір у фонову чергу та
замінив легкий англомовний sentiment на оцінений multilingual transformer».
