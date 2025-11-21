# Color Vacuum Playground

Небольшая песочница на `pygame`, в которой разноцветные шарики хаотично перемещаются по полю, смешиваются при контакте, а игрок с помощью курсора может «пылесосить» их в инвентарь и выпускать обратно. На поле также есть зона удаления: попавшие в неё шары исчезают и автоматически заменяются новыми, поэтому пространство всегда заполнено.

## Локальный запуск

- **Зависимости**: `Python 3.11+`, `pip`, системные библиотеки SDL2 (на Linux можно установить через `sudo apt install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev`), а также X-сервер/окно (на macOS — встроенный, на Windows — обычное окно).
- Установите Python-зависимость:
  ```bash
  pip install -r requirements.txt
  ```
- Запустите игру одной командой:
  ```bash
  python gui.py
  ```
  (можно также `python -m gui`, т.к. точка входа находится в `gui.py`).

## Docker

В репозитории лежит готовый `Dockerfile`, собирающий образ с Python, SDL2 и `pygame`. Игра запускается сразу при старте контейнера через `ENTRYPOINT ["python", "gui.py"]`.

### Сборка
```bash
docker build -t color-vacuum .
```

### Запуск (Linux host + X11)
```bash
xhost +local:docker
docker run --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  color-vacuum
```
- При необходимости ограничьте доступ обратно: `xhost -local:docker`.
- Если хотите задать другой путь к сокету X11, поправьте монтирование `-v`.

### Запуск на Windows/macOS

- **Windows**: установите X-сервер (VcXsrv/Xming) и запустите его. В настройках Docker Desktop включите проброс дисплея, затем запустите контейнер:
  ```powershell
  docker run --rm `
    -e DISPLAY=host.docker.internal:0.0 `
    color-vacuum
  ```
- **macOS**: при использовании Docker Desktop + XQuartz:
  ```bash
  xhost + 127.0.0.1
  docker run --rm \
    -e DISPLAY=host.docker.internal:0 \
    color-vacuum
  ```
  Убедитесь, что XQuartz разрешает входящие соединения от сетевых клиентов.

После запуска контейнера окно игры появится автоматически благодаря точке входа `gui.py`.

