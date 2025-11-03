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
        
        print(f"✅ Загружено {len(config)} параметров из конфигурации")
        return config
        
    except FileNotFoundError:
        print(f"❌ Ошибка: Конфигурационный файл '{config_path}' не найден")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка при чтении '{config_path}': {e}")
        sys.exit(1)

def validate_config(config):
    """
    Проверяет, что все необходимые параметры присутствуют в конфигурации
    """
    if config is None:
        print("❌ Ошибка: Конфигурация не загружена (None)")
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
        print(f"❌ Ошибка: В конфигурации отсутствуют обязательные поля: {', '.join(missing_fields)}")
        sys.exit(1)
    
    # Проверка типов данных
    if not isinstance(config['max_depth'], int) or config['max_depth'] < 1:
        print("❌ Ошибка: 'max_depth' должен быть положительным целым числом")
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
    print(f"📥 Скачивание файла пакетов: {url}")
    try:
        # Скачиваем файл
        with urllib.request.urlopen(url) as response:
            compressed_data = response.read()
        
        # Распаковываем gzip
        decompressed_data = gzip.decompress(compressed_data)
        content = decompressed_data.decode('utf-8')
        
        print("✅ Файл пакетов успешно загружен и распакован")
        return content
    except Exception as e:
        print(f"❌ Ошибка при загрузке файла пакетов: {e}")
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
        print(f"✅ Найдено зависимостей: {len(dependencies)}")
    else:
        print("ℹ️  Зависимости не найдены или пакет не существует")
    
    return dependencies

def stage2_collect_dependencies(config):
    """
    Этап 2: Сбор данных о зависимостях
    """
    print("\n" + "="*50)
    print("🚀 ЭТАП 2: Сбор данных о зависимостях")
    print("="*50)
    
    # Скачиваем и парсим файл пакетов
    packages_content = download_packages_file(config['repository_url'])
    if packages_content is None:
        return []
    
    # Ищем зависимости для указанного пакета
    dependencies = parse_package_dependencies(packages_content, config['package_name'])
    
    # Выводим зависимости (требование этапа)
    print(f"\n📦 Прямые зависимости пакета '{config['package_name']}':")
    if dependencies:
        for i, dep in enumerate(dependencies, 1):
            print(f"  {i}. {dep}")
    else:
        print("  (нет зависимостей)")
    
    return dependencies

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
    
    print("\n✅ Этап 2 завершен!")
    
    # Сохраняем зависимости для следующего этапа
    return config, dependencies

if __name__ == "__main__":
    config, dependencies = main()