# Проверенный доступ Upwork

Проверено 2026-11-06. Официальный сервер https://mcp.upwork.com/mcp; OAuth успешен. До ограничения: 50 инструментов. После: свежий app-server и текущий каталог этого чата показывают ровно четыре.

| enabled_tools | Действия | Доступ |
|---|---|---|
| upwork__list_accounts | discovery accounts | чтение |
| upwork__get_tool_help | описание и input_schema | чтение |
| upwork__get_profile | get, list_highlights, transactions, connects_balance | все читающие; задача использует get/list_highlights |
| upwork__find_jobs | search, get, smart_search | чтение |

Ограничение действует на инструменты, не отдельные действия. Финансовые чтения get_profile не нужны этой задаче. Инструментов записи в разрешённом каталоге нет. Остальные MCP не изменены.

Перед запуском сверять фактический каталог и выбирать TALENT/freelancer через list_accounts. Использовать текущую схему get_tool_help; не угадывать поля.

search: query — широкое семантическое совпадение; явно sort=recency; limit 1–10. Доступны job_type=fixed и budget_min (budget_min не фильтрует hourly), но с 22.11.2026 они не применяются: бюджет не порог отбора, поиск идёт без них. Фильтра даты у search нет — применять published_date/created_date локально. title — AND по словам, несовместим с query и relevance. smart_search:most_recent фильтрует дату, но персонализирован под текущий профиль. get принимает params.id и возвращает готовый URL, статус и детали. location_required=false — предпочтение, не жёсткое ограничение. Не угадывать причину can_apply=false.
