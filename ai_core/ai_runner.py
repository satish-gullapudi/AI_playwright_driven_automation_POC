import importlib
import asyncio
import pkgutil
import ai_tests
from ai_core.ai_logger import log_info

async def run_all_tests():
    log_info("🔍 Discovering AI test scripts...")

    for _, module_name, _ in pkgutil.iter_modules(ai_tests.__path__):
        log_info(f"🚀 Running test: {module_name}")
        module = importlib.import_module(f"ai_tests.{module_name}")
        if hasattr(module, "main"):
            try:
                await module.main()
                log_info(f"✅ Test Passed: {module_name}")
            except Exception as e:
                log_info(f"❌ Test Failed: {module_name} - {e}")
