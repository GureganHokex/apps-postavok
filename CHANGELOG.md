# История изменений

## [v0.2] — 2026-03-01

### Система авторизации и ролей

- **Три роли**: администратор, бармен, пользователь. Разграничение прав на API и в интерфейсе.
- **Админ-панель** — отдельная точка входа (`admin.html` / `?page=admin`): форма входа только для админа, после входа полный интерфейс.
- **API авторизации**: `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET /api/auth/me/`. Сессионная аутентификация, ответ с `user` и `is_admin`.
- **Backend**: модель `UserProfile` (роль), поле `Tap.is_visible`; миграции; команда `create_admin_user`; права доступа по ролям (IsAdmin, IsAdminOrBartender и др.).
- **Frontend**: контекст авторизации (AuthContext), формы входа, отображение вкладок и действий в зависимости от роли.

### Админ-панель (отдельная страница)

- **Маршрут `/admin`**: отдельная страница управления пользователями (не вкладка парсера).
- **Кнопка «Админ-панель»** в шапке рядом с «Выйти» (видна только администратору).
- **Управление пользователями**: список, добавление (логин, пароль, роль, имя, фамилия, email), редактирование (роль, имена, смена пароля), удаление. Запрет удаления самого себя.

### Backend

- **API пользователей** (только админ): `GET/POST /api/users/`, `PATCH/DELETE /api/users/:id/`. Сериализаторы UserSerializer, UserCreateSerializer, UserUpdateSerializer.
- **Обход CSRF для SPA**: `AuthLoginView` (authentication_classes = []), `AuthLogoutView` и `UserViewSet` с `SessionAuthenticationNoCSRF` для работы с фронтом с другого origin.
- **Парсеры и сессия**: для входа заданы `parser_classes = [JSONParser, FormParser]`; для `login()` используется оригинальный HttpRequest (`request._request`).
- **Миграции**: создание таблицы `django_session` и остальных при `migrate`.
- **CSRF_TRUSTED_ORIGINS**: по умолчанию добавлены `http://localhost:3000` и `http://127.0.0.1:3000` при пустом `DJANGO_CSRF_TRUSTED_ORIGINS`.

### Frontend

- **Роутинг**: React Router, маршруты `/` (парсер) и `/admin` (управление пользователями). Общий заголовок с ссылкой «Пивной импортер» на главную.
- **AdminPanel**: таблица пользователей, формы создания и редактирования, поддержка пагинированного ответа API (`data.results`).
- **QueryClientProvider** вынесен в LoggedInLayout, чтобы страница `/admin` имела доступ к React Query.

### Исправления

- Ошибка входа (403/500): отключение проверки CSRF и использование корректного request для login; явные parser_classes; таблица сессий через migrate.
- Ошибка выхода (403): отдельный view с SessionAuthenticationNoCSRF.
- Ошибка «users.map is not a function»: учёт пагинации DRF (`data.results`).
- Ошибка «No QueryClient set» в AdminPanel: общий QueryClientProvider для обоих маршрутов.
- Ошибки CSRF при сохранении в админ-таблице: SessionAuthenticationNoCSRF для UserViewSet и доверенные origins.

---

[v0.2]: https://github.com/GureganHokex/apps-postavok/releases/tag/v0.2
