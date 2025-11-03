import yaml
import sys
import os

def load_config(config_path="config.yaml"):
    """
    Загружает конфигурацию из YAML-файла
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config
    except FileNotFoundError:
        print(f"❌ Ошибка: Конфигурационный файл '{config_path}' не найден")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Ошибка: Неверный формат YAML в файле '{config_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка при чтении '{config_path}': {e}")
        sys.exit(1)

def validate_config(config):
    """
    Проверяет, что все необходимые параметры присутствуют в конфигурации
    """
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

def main():
    """
    Основная функция программы
    """
    print("🛠️  Загрузка конфигурации...")
    
    # Загружаем конфигурацию
    config = load_config()
    
    # Проверяем корректность конфигурации
    validate_config(config)
    
    # Выводим все параметры (требование этапа)
    print_config(config)
    
    # Здесь позже будет остальная логика
    print("✅ Конфигурация успешно загружена!")

if __name__ == "__main__":
    main()