from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="sp-comparison-tool",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="MS-SQL 저장 프로시저 결과 비교 도구",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/sp-comparison-tool",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires=">=3.10",
    install_requires=[
        "PySide6>=6.5.0",
        "pyodbc>=5.0.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "deepdiff>=6.3.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
        "colorlog>=6.7.0",
    ],
    entry_points={
        "console_scripts": [
            "sp-compare=main:main",
        ],
    },
)