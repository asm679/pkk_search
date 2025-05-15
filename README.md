# Проект "Кадастр CLI"

[![Статус сборки](https://github.com/asm679/pkk_search/actions/workflows/python-app.yml/badge.svg)](https://github.com/asm679/pkk_search/actions/workflows/python-app.yml) [![codecov](https://codecov.io/gh/asm679/pkk_search/graph/badge.svg?token=K7DPVHQTWR)](https://codecov.io/gh/asm679/pkk_search) [![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org) [![Лицензия: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Статус проекта: Активная разработка](https://img.shields.io/badge/status-active-green.svg)](https://github.com/asm679/pkk_search/pulse)

Командная утилита (CLI) на Python для обработки и анализа геоданных из KML-файлов, с акцентом на кадастровую информацию.

## 🗺️ Обзор и Возможности

Проект "Кадастр CLI" предоставляет набор инструментов для:
- Загрузки и парсинга KML файлов (версии 2.2).
- Извлечения геометрических данных (точки, линии, полигоны).
- Конвертации геометрий в формат Shapely для дальнейшего анализа.
- Вычисления геометрических характеристик: площадь, периметр, длина.
- Взаимодействия с API Росреестра (через НСПД) для получения кадастровой информации по текстовому запросу или координатам.
- Сохранения результатов в формате GeoJSON.

### 📈 Основной рабочий процесс

```mermaid
graph LR
    A[KML файл / Запрос к API] --> B{Парсер KML / Клиент API Росреестра};
    B -- Данные KML --> C[Объекты геометрии KML];
    B -- Данные API --> D[Кадастровые объекты НСПД];
    C --> E[Конвертация в Shapely];
    D -- Геометрия НСПД --> E;
    E --> F[Геометрическая обработка (площадь, длина, периметр)];
    F --> G[Вывод: консоль / GeoJSON файл];
    D -- Атрибуты НСПД --> G;
```

## 📚 Документация

Подробная документация по проекту доступна [здесь](docs/index.md).
Она включает:
- [Руководство пользователя](docs/user_guide/introduction.md)
- [Руководство для разработчиков](docs/developer_guide/overview.md)
- [Описание API](docs/api/index.md)
- [Стандарты документирования](docs/DOCUMENTATION_STANDARDS.md)
- [Руководство по участию в разработке документации](docs/CONTRIBUTING_DOCS.md)

## ⚙️ Установка

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/asm679/pkk_search.git
    cd pkk_search
    ```

2.  **Создайте и активируйте виртуальное окружение (рекомендуется):**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Использование

Основная команда для взаимодействия с утилитой - `kadastr_cli`.

**Примеры:**

Обработка KML файла:
```bash
python kadastr_cli.py process-kml --kml-file "Путь/К/Вашему/Файлу.kml" --geojson-output "output.geojson"
```

Поиск информации по кадастровому номеру или адресу через API Росреестра (НСПД):
```bash
python kadastr_cli.py search-pkk --query-text "Москва, ул. Тверская, д. 1"
python kadastr_cli.py search-pkk --query-text "77:01:0001001:1234" --shapely-wkt
```

Доступные команды и опции можно посмотреть с помощью:
```bash
python kadastr_cli.py --help
python kadastr_cli.py process-kml --help
python kadastr_cli.py search-pkk --help
```

## 🤝 Участие в разработке

Мы приветствуем вклад в развитие проекта! Пожалуйста, ознакомьтесь с нашим [Руководством по управлению версиями и участию в разработке](VERSION_CONTROL.md) и [Руководством по написанию документации](docs/CONTRIBUTING_DOCS.md) перед началом работы.

Основные этапы:
1. Ознакомьтесь с текущими задачами (обычно управляются через Task Master).
2. Создайте ветку из `develop` для вашей новой функциональности или исправления.
3. Напишите код и тесты.
4. Обновите или напишите документацию.
5. Сделайте Pull Request в ветку `develop`.

## 📄 Лицензия

Проект распространяется под лицензией MIT. См. файл `LICENSE`. 