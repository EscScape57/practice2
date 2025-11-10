import sys
import os
import urllib.request
import gzip

def load_config(config_path="config.yaml"):
    """
    Загружает конфигурацию из YAML-файла (упрощенная версия)
    """
    config = {}
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                # Ищем строки с ключ: значение
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Преобразование типов
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    else:
                        # Убираем кавычки если есть
                        value = value.strip('"\'')
                    
                    config[key] = value
        
        print(f" Загружено {len(config)} параметров из конфигурации")
        return config
        
    except FileNotFoundError:
        print(f" Ошибка: Конфигурационный файл '{config_path}' не найден")
        sys.exit(1)
    except Exception as e:
        print(f" Неожиданная ошибка при чтении '{config_path}': {e}")
        sys.exit(1)

def validate_config(config):
    """
    Проверяет, что все необходимые параметры присутствуют в конфигурации
    """
    if config is None:
        print(" Ошибка: Конфигурация не загружена (None)")
        sys.exit(1)
    
    required_fields = [
        'package_name',
        'repository_url',
        'test_mode',
        'output_image',
        'max_depth',
        'filter_substring'
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in config:
            missing_fields.append(field)
    
    if missing_fields:
        print(f" Ошибка: В конфигурации отсутствуют обязательные поля: {', '.join(missing_fields)}")
        sys.exit(1)
    
    # Проверка типов данных
    if not isinstance(config['max_depth'], int) or config['max_depth'] < 1:
        print(" Ошибка: 'max_depth' должен быть положительным целым числом")
        sys.exit(1)

def print_config(config):
    """
    Выводит все параметры конфигурации в формате ключ-значение
    """
    print("🔧 Текущая конфигурация:")
    print("-" * 40)
    for key, value in config.items():
        print(f"  {key}: {value}")
    print("-" * 40)

def download_packages_file(url):
    """
    Скачивает и распаковывает файл Packages.gz
    """
    print(f" Скачивание файла пакетов: {url}")
    try:
        # Добавляем таймаут
        with urllib.request.urlopen(url, timeout=30) as response:
            compressed_data = response.read()
        
        # Распаковываем gzip
        decompressed_data = gzip.decompress(compressed_data)
        content = decompressed_data.decode('utf-8')
        
        print(" Файл пакетов успешно загружен и распакован")
        return content
    except Exception as e:
        print(f" Ошибка при загрузке файла пакетов: {e}")
        return None

def parse_package_dependencies(packages_content, package_name):
    """
    Ищет зависимости для указанного пакета в содержимом Packages файла
    """
    print(f"🔍 Поиск пакета: {package_name}")
    
    lines = packages_content.split('\n')
    in_target_package = False
    dependencies = []
    
    for line in lines:
        # Находим начало секции нужного пакета
        if line.startswith('Package: ') and line[9:] == package_name:
            in_target_package = True
            continue
        
        # Если мы в секции нужного пакета, ищем зависимости
        if in_target_package:
            if line.startswith('Depends: '):
                # Извлекаем зависимости
                dep_line = line[9:]
                # Разбираем строку зависимостей (могут быть версии: libc6 (>= 2.34))
                raw_deps = dep_line.split(',')
                for dep in raw_deps:
                    dep = dep.strip()
                    # Берем только имя пакета (до первой скобки или пробела)
                    if ' (' in dep:
                        dep_name = dep.split(' (')[0].strip()
                    else:
                        dep_name = dep.split(' ')[0].strip()
                    if dep_name:
                        dependencies.append(dep_name)
            elif line.startswith('Package: '):
                # Начался следующий пакет - заканчиваем поиск
                break
    
    # Фильтруем пустые значения и дубликаты
    dependencies = list(set([dep for dep in dependencies if dep]))
    
    if dependencies:
        print(f" Найдено зависимостей: {len(dependencies)}")
    else:
        print("ℹ️  Зависимости не найдены или пакет не существует")
    
    return dependencies

def stage2_collect_dependencies(config):
    """
    Этап 2: Сбор данных о зависимостях
    """
    print("\n" + "="*50)
    print(" ЭТАП 2: Сбор данных о зависимостях")
    print("="*50)
    
    # Если тестовый режим, пропускаем скачивание
    if config['test_mode']:
        print(" Тестовый режим: пропуск скачивания пакетов")
        # Возвращаем пустой список, зависимости будут получены в Этапе 3
        return []
    
    # Реальный режим: скачиваем и парсим файл пакетов
    packages_content = download_packages_file(config['repository_url'])
    if packages_content is None:
        return []
    
    # Ищем зависимости для указанного пакета
    dependencies = parse_package_dependencies(packages_content, config['package_name'])
    
    # Выводим зависимости (требование этапа)
    print(f"\n Прямые зависимости пакета '{config['package_name']}':")
    if dependencies:
        for i, dep in enumerate(dependencies, 1):
            print(f"  {i}. {dep}")
    else:
        print("  (нет зависимостей)")
    
    return dependencies

def build_dependency_graph_bfs(config, start_package, initial_dependencies):
    """
    Строит полный граф зависимостей с помощью BFS
    """
    print(f"\n Построение графа зависимостей для '{start_package}'...")
    print(f"   Максимальная глубина: {config['max_depth']}")
    print(f"   Фильтр: '{config['filter_substring']}'")
    
    # Граф зависимостей {пакет: [зависимости]}
    graph = {start_package: initial_dependencies}
    # Очередь для BFS: (пакет, текущая_глубина)
    queue = []
    # Множество посещенных пакетов для избежания циклов
    visited = set([start_package])
    
    # Добавляем начальные зависимости в очередь
    for dep in initial_dependencies:
        if dep not in visited:
            queue.append((dep, 1))  # (пакет, глубина=1)
    
    # Скачиваем файл пакетов один раз (кэшируем)
    packages_content = None
    if not config['test_mode']:
        print("    Загрузка файла пакетов...")
        packages_content = download_packages_file(config['repository_url'])
        if not packages_content:
            print("    Не удалось загрузить файл пакетов")
            return graph
    
    # BFS обход
    while queue:
        current_package, current_depth = queue.pop(0)
        
        # Пропускаем если уже посещали
        if current_package in visited:
            continue
        
        visited.add(current_package)
        
        # Проверяем максимальную глубину
        if current_depth >= config['max_depth']:
            print(f"   Пропуск '{current_package}' (достигнута максимальная глубина)")
            graph[current_package] = []
            continue
        
        # Фильтруем пакеты по подстроке
        if config['filter_substring'] and config['filter_substring'] in current_package:
            print(f"   Пропуск '{current_package}' (фильтр: '{config['filter_substring']}')")
            graph[current_package] = []
            continue
        
        print(f"    Анализ пакета '{current_package}' (глубина {current_depth})...")
        
        # Получаем зависимости для текущего пакета
        try:
            if config['test_mode']:
                # Тестовый режим - используем тестовые данные
                dependencies = get_test_dependencies(current_package)
            else:
                # Реальный режим - парсим из скачанного файла
                dependencies = parse_package_dependencies(packages_content, current_package)
            
            graph[current_package] = dependencies
            
            # Добавляем зависимости в очередь для дальнейшего обхода
            for dep in dependencies:
                if dep not in visited:
                    queue.append((dep, current_depth + 1))
                    
        except Exception as e:
            print(f"    Ошибка при анализе '{current_package}': {e}")
            graph[current_package] = []
    
    print(f" Граф построен! Всего пакетов: {len(graph)}")
    return graph

def get_test_dependencies(package):
    """
    Возвращает тестовые зависимости для демонстрации
    """
    test_data = {
        "A": ["B", "C", "D"],
        "B": ["E", "F"],
        "C": ["G", "H"],
        "D": ["I", "J"],
        "E": ["K", "L"],
        "F": ["M", "N"],
        "G": ["O", "P"],
        "H": ["Q", "R"]
    }
    return test_data.get(package, [])

def test_mode_parse_dependencies(file_path, start_package):
    """
    Режим тестирования: парсит зависимости из тестового файла
    """
    print(f" Тестовый режим: чтение из файла {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Простой формат: A: B, C, D
        graph = {}
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line and ':' in line:
                package, deps_str = line.split(':', 1)
                package = package.strip()
                dependencies = [dep.strip() for dep in deps_str.split(',')]
                graph[package] = [d for d in dependencies if d]  # Фильтруем пустые
        
        # Получаем зависимости для стартового пакета
        if start_package in graph:
            initial_deps = graph[start_package]
            print(f" Найдены зависимости для '{start_package}': {initial_deps}")
            return graph, initial_deps
        else:
            print(f" Пакет '{start_package}' не найден в тестовом файле")
            return graph, []
            
    except FileNotFoundError:
        print(f" Тестовый файл '{file_path}' не найден")
        return {}, []
    except Exception as e:
        print(f" Ошибка чтения тестового файла: {e}")
        return {}, []

def stage3_build_dependency_graph(config, initial_dependencies):
    """
    Этап 3: Построение полного графа зависимостей
    """
    print("\n" + "="*50)
    print(" ЭТАП 3: Построение графа зависимостей")
    print("="*50)
    
    if config['test_mode']:
        print(" ТЕСТОВЫЙ РЕЖИМ")
        # В тестовом режиме получаем начальные зависимости из тестового файла
        graph, deps_from_file = test_mode_parse_dependencies(
            config['repository_url'],  # путь к тестовому файлу
            config['package_name']
        )
        if deps_from_file:
            graph = build_dependency_graph_bfs(config, config['package_name'], deps_from_file)
        else:
            graph = build_dependency_graph_bfs(config, config['package_name'], [])
    else:
        print(" РЕАЛЬНЫЙ РЕЖИМ")
        # В реальном режиме используем зависимости из Этапа 2
        graph = build_dependency_graph_bfs(config, config['package_name'], initial_dependencies)
    
    # Выводим статистику графа
    print(f"\n Статистика графа:")
    print(f"   Всего пакетов: {len(graph)}")
    total_dependencies = sum(len(deps) for deps in graph.values())
    print(f"   Всего зависимостей: {total_dependencies}")
    
    # Выводим граф в читаемом формате
    print(f"\n Граф зависимостей:")
    for package, deps in sorted(graph.items()):
        if deps:
            print(f"   {package} -> {', '.join(deps)}")
        else:
            print(f"   {package} -> (нет зависимостей)")
    
    return graph

def find_reverse_dependencies(graph, target_package):
    """
    Находит обратные зависимости - пакеты, которые зависят от target_package
    """
    print(f" Поиск обратных зависимостей для '{target_package}' в построенном графе...")
    
    reverse_deps = []
    
    # Проходим по всем пакетам в графе
    for package, dependencies in graph.items():
        # Если target_package есть в зависимостях этого пакета
        if target_package in dependencies:
            reverse_deps.append(package)
    
    print(f" Найдено обратных зависимостей в графе: {len(reverse_deps)}")
    return reverse_deps

def find_reverse_dependencies_advanced(config, target_package):
    """
    Находит обратные зависимости анализируя ВСЕ пакеты в репозитории
    """
    print(f"🔍 Расширенный поиск обратных зависимостей для '{target_package}'...")
    
    # Скачиваем полный файл пакетов
    packages_content = download_packages_file(config['repository_url'])
    if not packages_content:
        return []
    
    reverse_deps = []
    lines = packages_content.split('\n')
    current_package = None
    current_dependencies = []
    
    # Парсим все пакеты в репозитории
    for line in lines:
        line = line.strip()
        
        if line.startswith('Package: '):
            # Сохраняем предыдущий пакет если он зависит от target_package
            if current_package and target_package in current_dependencies:
                reverse_deps.append(current_package)
            
            # Начинаем новый пакет
            current_package = line[9:]
            current_dependencies = []
            
        elif line.startswith('Depends: '):
            # Парсим зависимости текущего пакета
            dep_line = line[9:]
            raw_deps = dep_line.split(',')
            for dep in raw_deps:
                dep = dep.strip()
                if ' (' in dep:
                    dep_name = dep.split(' (')[0].strip()
                else:
                    dep_name = dep.split(' ')[0].strip()
                if dep_name:
                    current_dependencies.append(dep_name)
    
    # Проверяем последний пакет
    if current_package and target_package in current_dependencies:
        reverse_deps.append(current_package)
    
    # Убираем дубликаты и сортируем
    reverse_deps = sorted(list(set(reverse_deps)))
    
    print(f" Найдено обратных зависимостей в репозитории: {len(reverse_deps)}")
    return reverse_deps

def stage4_reverse_dependencies(config, graph):
    """
    Этап 4: Поиск обратных зависимостей
    """
    print("\n" + "="*50)
    print(" ЭТАП 4: Поиск обратных зависимостей")
    print("="*50)
    
    # Способ 1: Быстрый поиск в уже построенном графе (ограниченный)
    simple_reverse_deps = find_reverse_dependencies(graph, config['package_name'])
    
    # Способ 2: Расширенный поиск по всему репозиторию (полный)
    print("\n--- РАСШИРЕННЫЙ ПОИСК ---")
    full_reverse_deps = find_reverse_dependencies_advanced(config, config['package_name'])
    
    # Выводим результаты
    print(f"\n Пакеты, зависящие от '{config['package_name']}':")
    
    if full_reverse_deps:
        print(f" Всего найдено: {len(full_reverse_deps)} пакетов")
        print("\n Первые 20 пакетов:")
        for i, package in enumerate(full_reverse_deps[:20], 1):
            print(f"  {i}. {package}")
        
        if len(full_reverse_deps) > 20:
            print(f"  ... и еще {len(full_reverse_deps) - 20} пакетов")
    else:
        print("  (нет обратных зависимостей)")
    
    return full_reverse_deps

import subprocess
import tempfile
import os

def generate_dot_graph(graph, main_package):
    """
    Генерирует DOT-код для Graphviz из графа зависимостей
    """
    print(" Генерация DOT-кода для визуализации...")
    
    dot_lines = [
        "digraph Dependencies {",
        "    rankdir=TB;",
        "    node [shape=box, style=filled, fillcolor=lightblue];",
        "    edge [color=darkgreen];",
        "    concentrate=true;",
        ""
    ]
    
    # Добавляем главный пакет с другим цветом
    dot_lines.append(f'    "{main_package}" [fillcolor=orange, style=filled];')
    dot_lines.append("")
    
    # Добавляем все зависимости
    for package, dependencies in sorted(graph.items()):
        for dep in dependencies:
            dot_lines.append(f'    "{package}" -> "{dep}";')
    
    dot_lines.append("}")
    
    dot_content = "\n".join(dot_lines)
    print(" DOT-код сгенерирован")
    return dot_content

def save_graph_image(config, graph):
    """
    Сохраняет граф в PNG файл используя Graphviz
    """
    print(f" Сохранение графа в файл: {config['output_image']}")
    
    # Генерируем DOT-код
    dot_content = generate_dot_graph(graph, config['package_name'])
    
    try:
        # Создаем временный DOT-файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as dot_file:
            dot_file.write(dot_content)
            dot_path = dot_file.name
        
        # Конвертируем DOT в PNG используя Graphviz
        result = subprocess.run([
            'dot', '-Tpng', dot_path, '-o', config['output_image']
        ], capture_output=True, text=True)
        
        # Удаляем временный DOT-файл
        os.unlink(dot_path)
        
        if result.returncode == 0:
            print(f" Граф успешно сохранен в {config['output_image']}")
            return True
        else:
            print(f" Ошибка Graphviz: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print(" Graphviz не установлен. Установите: 'brew install graphviz' или 'apt install graphviz'")
        return False
    except Exception as e:
        print(f" Ошибка при сохранении графа: {e}")
        return False

def generate_text_visualization(graph, main_package):
    """
    Создает текстовую визуализацию графа в виде дерева
    """
    print("🔄 Генерация текстовой визуализации...")
    
    def build_tree(package, depth=0, visited=None):
        if visited is None:
            visited = set()
        
        if package in visited:
            return f"{'  ' * depth}└── {package} ⤴ (цикл)\n"
        
        visited.add(package)
        
        tree = f"{'  ' * depth}└── {package}\n"
        
        if package in graph and graph[package]:
            for i, dep in enumerate(graph[package]):
                if i == len(graph[package]) - 1:
                    tree += build_tree(dep, depth + 1, visited.copy())
                else:
                    tree += build_tree(dep, depth + 1, visited.copy())
        
        return tree
    
    tree_visualization = f" Дерево зависимостей для '{main_package}':\n"
    tree_visualization += build_tree(main_package)
    
    return tree_visualization

def stage5_visualization(config, graph):
    """
    Этап 5: Визуализация графа зависимостей
    Требование: Сформировать текстовое представление графа на языке диаграмм Graphviz
    """
    print("\n" + "="*50)
    print(" ЭТАП 5: Визуализация графа")
    print("="*50)
    
    # Генерируем полный DOT-код
    print(" Формирование текстового представления графа на языке Graphviz...")
    dot_content = generate_dot_graph(graph, config['package_name'])
    
    # СОХРАНЯЕМ полный DOT-код в файл (требование)
    dot_filename = config['output_image'].replace('.png', '.dot')
    try:
        with open(dot_filename, 'w', encoding='utf-8') as f:
            f.write(dot_content)
        print(f" Полный DOT-код сохранен в файл: {dot_filename}")
    except Exception as e:
        print(f" Ошибка сохранения DOT-файла: {e}")
        return False
    
    # ВЫВОДИМ полное текстовое представление на языке Graphviz (требование этапа)
    print(f"\n ПОЛНОЕ ТЕКСТОВОЕ ПРЕДСТАВЛЕНИЕ ГРАФА НА ЯЗЫКЕ GRAPHVIZ:")
    print("=" * 80)
    print(dot_content)
    print("=" * 80)
    
    # Дополнительная информация
    print(f"\n Статистика визуализации:")
    print(f"   • Главный пакет: {config['package_name']}")
    print(f"   • Всего пакетов в графе: {len(graph)}")
    print(f"   • Всего зависимостей: {sum(len(deps) for deps in graph.values())}")
    print(f"   • Файл с DOT-кодом: {dot_filename}")
    
    # Инструкции для визуализации
    print(f"\n Инструкции для визуализации:")
    print(f"   1. Скопируйте ВЕСЬ текст выше (между линиями ====)")
    print(f"   2. Перейдите на https://edotor.net/")
    print(f"   3. Вставьте скопированный текст в левую панель")
    print(f"   4. Нажмите кнопку 'Generate Graph'")
    print(f"   5. ИЛИ используйте файл: {dot_filename}")
    
    return True

def main():
    """
    Основная функция программы
    """
    print("🛠️  Загрузка конфигурации...")
    
    # Загружаем конфигурацию
    config = load_config()
    
    # Проверяем корректность конфигурации
    validate_config(config)
    
    # Выводим все параметры (требование этапа 1)
    print_config(config)
    
    # Этап 2: Сбор данных о зависимостях
    dependencies = stage2_collect_dependencies(config)
    
    # Этап 3: Построение полного графа зависимостей
    graph = stage3_build_dependency_graph(config, dependencies)
    
    # Этап 4: Поиск обратных зависимостей
    reverse_deps = stage4_reverse_dependencies(config, graph)
    
    # Этап 5: Визуализация графа
    visualization_success = stage5_visualization(config, graph)
    
    print("\n Все этапы завершены!")
    
    return config, dependencies, graph, reverse_deps, visualization_success

if __name__ == "__main__":
    config, dependencies, graph, reverse_deps, visualization_success = main()