#!/usr/bin/env python3
"""
使用大模型agent调用基于javaParser实现的java源码分析服务,对java进行源码分析、并输出测试点建议和典型测试用例。

使用方式:
    python agent/java_code_analyzer_agent.py <repo_path> <base_commit> <new_commit>如:
    python java_code_analyzer/run_java_code_analyzer_agent.py /Users/zhangxiaoguo/Documents/education-service 95291763 4cbb6ab4 --model deepseek-chat
"""

import sys
import os
import argparse
from pathlib import Path
from tools import GitTools

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.ai_agents.java_code_analyzer.java_code_analyzer_agent import JavaCodeAnalyzerAgent


def main():
    """运行分析"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="使用 LangChain 框架运行测试范围分析 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("repo_path", nargs='?', help="Java 项目路径", default="/Users/zhangxiaoguo/Documents/java-callgraph2")
    parser.add_argument("base_commit", nargs='?', help="基准 commit 哈希", default="75f4c93a")
    parser.add_argument("new_commit", nargs='?', help="新 commit 哈希", default="20b84145")
    parser.add_argument("--java_analyzer_service_url", help="java源码分析 API 地址")
    parser.add_argument("--max-iterations", type=int, help="最大迭代次数", default=300)
    parser.add_argument("--model", help="模型名称（覆盖环境变量）")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")
    
    args = parser.parse_args()
    
    # 获取 API 密钥
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 错误: 未设置 OPENAI_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)
    
    base_url = os.getenv("OPENAI_BASE_URL")
    model = args.model or os.getenv("OPENAI_MODEL", "deepseek-reasoner")
    
    print("="*70)
    print("🤖 LangChain 测试范围分析 Agent")
    print("="*70)
    print(f"📁 项目路径: {args.repo_path}")
    print(f"🔄 变更范围: {args.base_commit[:8]} → {args.new_commit[:8]}")
    print(f"🧠 使用模型: {model}")
    if base_url:
        print(f"🌐 API 地址: {base_url}")
    print(f"🔧 分析服务: {args.api_url}")
    print("="*70)
    print()

    # 拉取最新代码
    git_tools = GitTools(args.repo_path)
    print("\n🔄 拉取最新代码...")
    git_tools.pull_latest() 

    # 记录原始版本
    print("\n🔍 记录当前 Git 状态...")
    original_ref = git_tools.get_current_ref()
    print(f"   当前引用: {original_ref}")
    
    # 初始化 Agent
    try:
        # 切换到目标版本
        print(f"\n🔄 切换到目标版本: {args.new_commit}")
        git_tools.checkout_version(args.new_commit)
        print(f"✅ 已切换到: {args.new_commit}")

        agent = JavaCodeAnalyzerAgent(
            repo_path=args.repo_path,
            api_key=api_key,
            base_url=base_url,
            model=model,
            java_analyzer_service_url=args.api_url,
            max_iterations=args.max_iterations,
            verbose=not args.quiet
        )
        print("✓ Agent 初始化成功")
    except Exception as e:
        print(f"❌ Agent 初始化失败: {e}", file=sys.stderr)
        sys.exit(1)
    
    print("\n" + "="*70)
    print("🚀 开始分析...")
    print("="*70)
    print()
    
    # 执行分析
    try:
        result = agent.analyze(args.base_commit, args.new_commit)
        
        if result["success"]:
            print("\n" + "="*70)
            # print("📊 分析报告")
            # print("="*70)
            # print(result["output"])
            
            # 保存报告
            if args.output:
                output_path = Path(args.output)
            else:
                output_path = Path(f"langchain_analysis_{args.base_commit[:8]}_{args.new_commit[:8]}.md")
            
            output_path.write_text(result["output"], encoding='utf-8')
            print(f"\n✓ 报告已保存到: {output_path}")
        else:
            print(f"\n❌ 分析失败: {result.get('error', '未知错误')}")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  分析被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 分析失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\n" + "="*70)
        print("✅ 分析完成!")
        print("="*70)
        # 恢复原始版本
        print(f"\n🔄 恢复到原始版本: {original_ref}")
        GitTools(args.repo_path).checkout_version(original_ref)
        print(f"✅ 已恢复到: {original_ref}")




if __name__ == "__main__":
    main()
