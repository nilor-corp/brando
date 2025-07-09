#!/usr/bin/env python3
"""
Test script for Brando app setup
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_comfyui_connection():
    """Test connection to ComfyUI"""
    comfy_ip = os.getenv("COMFY_IP", "127.0.0.1")
    comfy_port = os.getenv("COMFY_PORT", "8188")
    comfy_url = f"http://{comfy_ip}:{comfy_port}"

    print(f"Testing ComfyUI connection to {comfy_url}")

    try:
        # Test basic connection
        response = requests.get(f"{comfy_url}/system_stats", timeout=5)
        if response.status_code == 200:
            print("✅ ComfyUI connection successful")
            return True
        else:
            print(f"❌ ComfyUI returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to ComfyUI")
        print("   Make sure ComfyUI is running and accessible")
        return False
    except Exception as e:
        print(f"❌ Error connecting to ComfyUI: {e}")
        return False


def test_workflow_system():
    """Test workflow system"""
    print("\nTesting workflow system...")

    try:
        from workflows import get_workflow, execute_workflow

        # Test getting workflows
        logo_workflow = get_workflow("logo_to_video")
        upscale_workflow = get_workflow("upscale")

        if logo_workflow and upscale_workflow:
            print("✅ Workflow definitions loaded successfully")
        else:
            print("❌ Failed to load workflow definitions")
            return False

        # Test workflow execution
        test_inputs = {
            "logo": "test_logo.png",
            "pixel_map": "test_map.png",
            "reference_images": ["ref1.png", "ref2.png"],
            "text_prompt": "test prompt",
        }

        workflow_data = execute_workflow("logo_to_video", test_inputs)
        if workflow_data:
            print("✅ Workflow execution test successful")
            return True
        else:
            print("❌ Workflow execution test failed")
            return False

    except Exception as e:
        print(f"❌ Error testing workflow system: {e}")
        return False


def test_file_structure():
    """Test required file structure"""
    print("\nTesting file structure...")

    required_files = [
        "app.py",
        "workflows.py",
        "requirements.txt",
        "env.example",
        "brando.css",
    ]

    required_dirs = ["workflows", "uploads"]

    all_good = True

    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} (missing)")
            all_good = False

    for dir in required_dirs:
        if os.path.exists(dir):
            print(f"✅ {dir}/")
        else:
            print(f"❌ {dir}/ (missing)")
            all_good = False

    return all_good


def test_dependencies():
    """Test if required dependencies are available"""
    print("\nTesting dependencies...")

    required_packages = [
        "gradio",
        "requests",
        "websocket-client",
        "python-dotenv",
        "Pillow",
    ]

    all_good = True

    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (not installed)")
            all_good = False

    return all_good


def main():
    """Run all tests"""
    print("Brando App Setup Test")
    print("=" * 30)

    tests = [
        ("File Structure", test_file_structure),
        ("Dependencies", test_dependencies),
        ("ComfyUI Connection", test_comfyui_connection),
        ("Workflow System", test_workflow_system),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 30)
    print("TEST SUMMARY")
    print("=" * 30)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Brando app is ready to run.")
        print("Run 'python app.py' to start the application.")
    else:
        print(
            "\n⚠️  Some tests failed. Please fix the issues above before running the app."
        )

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
