#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации генерации сообщений с использованием DeepSeek.
Перед запуском убедитесь, что у вас есть API ключ DeepSeek в переменной окружения DEEPSEEK_API_KEY.
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем путь к скриптам
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Проверяем наличие API ключа
if not os.getenv("DEEPSEEK_API_KEY"):
    print("❌ Ошибка: DEEPSEEK_API_KEY не найден в переменных окружения.")
    print("Добавьте ключ в файл .env или установите переменную окружения:")
    print("export DEEPSEEK_API_KEY='ваш_ключ_здесь'")
    sys.exit(1)

from data.scripts.generate_deepseek import DeepSeekDatasetGenerator

def main():
    """Основная функция демонстрации"""
    print("🚀 Запуск теста генерации сообщений с DeepSeek")
    print("=" * 60)
    
    try:
        # Инициализируем генератор
        generator = DeepSeekDatasetGenerator(
            personas_path="data/config/personas.json",
            taxonomy_path="data/config/taxonomy.json",
        )
        
        print("✅ Генератор инициализирован")
        print(f"📊 Загружено персон: {len(generator.personas)}")
        print(f"📊 Загружено категорий: {len(generator.categories)}")
        
        # Демонстрация: генерируем несколько примеров
        print("\n🎭 Примеры генерации для разных персон и категорий:")
        print("-" * 60)
        
        # Пример 1: High-Achiever с техническими проблемами
        print("\n1. High-Achiever (A) → Технические проблемы (tech_issue):")
        persona_a = generator.get_persona_by_id("A")
        category_tech = generator.get_category_by_id("tech_issue")
        sample1 = generator._generate_ticket(persona_a, category_tech)
        if sample1:
            print(f"   Текст: {sample1['ticket_text']}")
        
        # Пример 2: Parent с вопросами об оплате
        print("\n2. Parent (D) → Договоры и оплата (finance_contracts):")
        persona_d = generator.get_persona_by_id("D")
        category_finance = generator.get_category_by_id("finance_contracts")
        sample2 = generator._generate_ticket(persona_d, category_finance)
        if sample2:
            print(f"   Текст: {sample2['ticket_text']}")
        
        # Пример 3: Tech-Skeptic с проверкой статуса
        print("\n3. Tech-Skeptic (C) → Проверка статуса (status_check):")
        persona_c = generator.get_persona_by_id("C")
        category_status = generator.get_category_by_id("status_check")
        sample3 = generator._generate_ticket(persona_c, category_status)
        if sample3:
            print(f"   Текст: {sample3['ticket_text']}")
        
        print("\n" + "=" * 60)
        print("✅ Тест завершен успешно!")
        print("\n📝 Для генерации полного датасета запустите:")
        print("   python data/scripts/generate_deepseek.py")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()