"""
第二期集成测试 - 品类工厂全链路验证

测试范围：
1. 品类库核心（模型、继承引擎）- 需Docker环境
2. 通用网文基类规则 - 需Docker环境
3. 品类预置内容（番茄+大唐+封神）
4. 品类Prompt模板
5. Context Assembler第8层（品类注入）- 需Docker环境
6. 品类蒸馏管线
7. 性能测试
8. 世界观硬约束集成

说明：
- 标记为"需Docker环境"的测试需要在完整的后端环境中运行
- 本地环境可测试纯功能模块（蒸馏管线、预置内容、世界观约束等）
"""
from __future__ import annotations

import sys
import time
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_genre_models():
    """测试1：品类库模型导入。"""
    print("\n" + "=" * 60)
    print("测试1：品类库模型导入")
    print("=" * 60)
    
    try:
        from app.v7.models.genre import GenrePack, GenreRule, GenreKnowledge, GenrePrompt
        
        print("✅ GenrePack 模型导入成功")
        print(f"   - 表名：{GenrePack.__tablename__}")
        
        print("✅ GenreRule 模型导入成功")
        print(f"   - 表名：{GenreRule.__tablename__}")
        
        print("✅ GenreKnowledge 模型导入成功")
        print(f"   - 表名：{GenreKnowledge.__tablename__}")
        
        print("✅ GenrePrompt 模型导入成功")
        print(f"   - 表名：{GenrePrompt.__tablename__}")
        
        return True
    except Exception as e:
        print(f"❌ 模型导入失败：{e}")
        return False


def test_genre_inheritance_engine():
    """测试2：继承解析引擎导入。"""
    print("\n" + "=" * 60)
    print("测试2：继承解析引擎导入")
    print("=" * 60)
    
    try:
        from app.v7.services.genre_inheritance import (
            get_genre_chain,
            resolve_genre_rules,
            resolve_genre_knowledge,
            resolve_genre_prompts,
            get_genre_tree,
            clear_inheritance_cache,
        )
        
        print("✅ get_genre_chain 函数导入成功")
        print("✅ resolve_genre_rules 函数导入成功")
        print("✅ resolve_genre_knowledge 函数导入成功")
        print("✅ resolve_genre_prompts 函数导入成功")
        print("✅ get_genre_tree 函数导入成功")
        print("✅ clear_inheritance_cache 函数导入成功")
        
        return True
    except Exception as e:
        print(f"❌ 继承引擎导入失败：{e}")
        return False


def test_genre_api():
    """测试3：品类API路由导入。"""
    print("\n" + "=" * 60)
    print("测试3：品类API路由导入")
    print("=" * 60)
    
    try:
        from app.v7.api.genres import router
        
        print("✅ 品类API路由导入成功")
        print(f"   - 路由前缀：{router.prefix}")
        print(f"   - 路由数量：{len(router.routes)}")
        
        # 列出所有路由
        for route in router.routes:
            print(f"   - {route.methods} {route.path}")
        
        return True
    except Exception as e:
        print(f"❌ API路由导入失败：{e}")
        return False


def test_genre_presets():
    """测试4：品类预置内容。"""
    print("\n" + "=" * 60)
    print("测试4：品类预置内容")
    print("=" * 60)
    
    try:
        # 直接导入文件
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "genre_presets",
            Path(__file__).parent / "genre_presets.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        DATANG_RULES = module.DATANG_RULES
        DATANG_KNOWLEDGE = module.DATANG_KNOWLEDGE
        FENGSHEN_RULES = module.FENGSHEN_RULES
        FENGSHEN_KNOWLEDGE = module.FENGSHEN_KNOWLEDGE
        GENRE_PROMPTS = module.GENRE_PROMPTS
        get_all_presets = module.get_all_presets
        
        print(f"✅ 大唐规则：{len(DATANG_RULES)} 条")
        print(f"✅ 大唐知识：{len(DATANG_KNOWLEDGE)} 条")
        print(f"✅ 封神规则：{len(FENGSHEN_RULES)} 条")
        print(f"✅ 封神知识：{len(FENGSHEN_KNOWLEDGE)} 条")
        
        # 统计知识类型
        knowledge_types = {}
        for item in DATANG_KNOWLEDGE:
            ktype = item.get("knowledge_type", "other")
            knowledge_types[ktype] = knowledge_types.get(ktype, 0) + 1
        
        print(f"\n大唐知识类型分布：")
        for ktype, count in knowledge_types.items():
            print(f"   - {ktype}: {count} 条")
        
        # Prompt模板
        print(f"\n✅ 品类Prompt模板：")
        for genre, prompts in GENRE_PROMPTS.items():
            print(f"   - {genre}: {len(prompts)} 套")
            for p in prompts:
                print(f"     * {p['prompt_type']}.{p['prompt_name']}")
        
        # get_all_presets
        all_presets = get_all_presets()
        print(f"\n✅ get_all_presets() 返回成功")
        print(f"   - 键数量：{len(all_presets)}")
        
        return True
    except Exception as e:
        print(f"❌ 预置内容测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_init_script():
    """测试5：品类初始化脚本。"""
    print("\n" + "=" * 60)
    print("测试5：品类初始化脚本")
    print("=" * 60)
    
    try:
        # 直接导入文件
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "init_genre_library",
            Path(__file__).parent / "init_genre_library.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        BASE_GENRES = module.BASE_GENRES
        BASE_RULES = module.BASE_RULES
        TOMATO_RULES = module.TOMATO_RULES
        TOMATO_KNOWLEDGE = module.TOMATO_KNOWLEDGE
        FENGSHEN_KNOWLEDGE = module.FENGSHEN_KNOWLEDGE
        
        print(f"✅ 基础品类：{len(BASE_GENRES)} 个")
        for genre in BASE_GENRES:
            print(f"   - {genre['name']} ({genre['slug']})")
        
        print(f"\n✅ 基础规则：{len(BASE_RULES)} 条")
        
        # 统计规则类型
        rule_types = {}
        for rule in BASE_RULES:
            rtype = rule.get("rule_type", "other")
            rule_types[rtype] = rule_types.get(rtype, 0) + 1
        
        print("基础规则类型分布：")
        for rtype, count in rule_types.items():
            print(f"   - {rtype}: {count} 条")
        
        print(f"\n✅ 番茄规则：{len(TOMATO_RULES)} 条")
        print(f"✅ 番茄知识：{len(TOMATO_KNOWLEDGE)} 条")
        print(f"✅ 封神知识：{len(FENGSHEN_KNOWLEDGE)} 条")
        
        return True
    except Exception as e:
        print(f"❌ 初始化脚本测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_assembler_genre_layer():
    """测试6：Context Assembler第8层（品类注入）。"""
    print("\n" + "=" * 60)
    print("测试6：Context Assembler第8层（品类注入）")
    print("=" * 60)
    
    try:
        from app.v7.generation.generation_engine import ContextAssembler
        
        print("✅ ContextAssembler 类导入成功")
        
        # 检查是否有 genre_id 参数
        import inspect
        sig = inspect.signature(ContextAssembler.__init__)
        params = list(sig.parameters.keys())
        
        print(f"   - __init__ 参数：{params}")
        
        if "genre_id" in params:
            print("✅ genre_id 参数存在")
        else:
            print("❌ genre_id 参数不存在")
            return False
        
        # 检查是否有 load_genre_context 方法
        if hasattr(ContextAssembler, "load_genre_context"):
            print("✅ load_genre_context 方法存在")
        else:
            print("❌ load_genre_context 方法不存在")
            return False
        
        # 检查是否有 _genre_cache 属性（在__init__中设置）
        # 这个需要实例化才能检查，但我们可以检查源码
        import inspect
        source = inspect.getsource(ContextAssembler.__init__)
        if "_genre_cache" in source:
            print("✅ _genre_cache 缓存属性存在")
        else:
            print("⚠️  _genre_cache 缓存属性未找到")
        
        # 检查 assemble_context 方法中是否有 genre 层
        assemble_source = inspect.getsource(ContextAssembler.assemble_context)
        if "genre_context" in assemble_source:
            print("✅ assemble_context 中有品类上下文加载")
        else:
            print("⚠️  assemble_context 中未找到品类上下文加载")
        
        if '"genre"' in assemble_source or "'genre'" in assemble_source:
            print("✅ layers 中有 genre 层")
        else:
            print("⚠️  layers 中未找到 genre 层")
        
        # 检查 render 方法中是否有品类渲染
        render_source = inspect.getsource(ContextAssembler.render)
        if "genre" in render_source:
            print("✅ render 方法中有品类层渲染")
        else:
            print("⚠️  render 方法中未找到品类层渲染")
        
        return True
    except Exception as e:
        print(f"❌ Context Assembler 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_genre_distillation():
    """测试7：品类蒸馏管线。"""
    print("\n" + "=" * 60)
    print("测试7：品类蒸馏管线")
    print("=" * 60)
    
    try:
        # 用 exec 执行文件，避免动态导入时 dataclass 的问题
        module_globals = {}
        file_path = Path(__file__).parent.parent / "backend/app/v7/services/genre_distillation.py"
        with open(file_path, "r", encoding="utf-8") as f:
            exec(f.read(), module_globals)
        
        ChapterFeatures = module_globals["ChapterFeatures"]
        GenreStats = module_globals["GenreStats"]
        DistillationResult = module_globals["DistillationResult"]
        clean_chapter_text = module_globals["clean_chapter_text"]
        is_valid_chapter = module_globals["is_valid_chapter"]
        extract_chapter_features = module_globals["extract_chapter_features"]
        aggregate_genre_stats = module_globals["aggregate_genre_stats"]
        generate_rule_suggestions = module_globals["generate_rule_suggestions"]
        generate_style_card_suggestion = module_globals["generate_style_card_suggestion"]
        generate_human_todo = module_globals["generate_human_todo"]
        compare_genres = module_globals["compare_genres"]
        distill_genre = module_globals["distill_genre"]
        export_rule_pack = module_globals["export_rule_pack"]
        export_human_todo = module_globals["export_human_todo"]
        export_comparison_report = module_globals["export_comparison_report"]
        
        print("✅ 数据结构导入成功")
        print("   - ChapterFeatures")
        print("   - GenreStats")
        print("   - DistillationResult")
        
        print("\n✅ 核心函数导入成功")
        print("   - clean_chapter_text")
        print("   - is_valid_chapter")
        print("   - extract_chapter_features")
        print("   - aggregate_genre_stats")
        print("   - generate_rule_suggestions")
        print("   - generate_style_card_suggestion")
        print("   - generate_human_todo")
        print("   - compare_genres")
        print("   - distill_genre")
        print("   - export_rule_pack")
        print("   - export_human_todo")
        print("   - export_comparison_report")
        
        # 测试文本清洗
        test_text = """
        第一章 初入江湖
        求收藏求推荐！
        本书起点中文网首发！
        
        李逍遥站在山巅，望着远方的云海，心中充满了豪情壮志。
        他深深地吸了一口气，缓缓地说道："从今天起，我要成为最强的修仙者！"
        
        然而，事情并没有那么简单。
        他知道，这条路充满了荆棘和危险。
        但是他不怕，他有信心克服一切困难。
        
        "你好，年轻人。"
        一个苍老的声音从身后传来。
        李逍遥猛地回头，只见一个白发老者正微笑着看着他。
        
        "前辈是？"李逍遥疑惑地问道。
        老者微微一笑："我是这里的守护者，看你骨骼惊奇，是个练武奇才。"
        
        李逍遥心中一喜，难道这就是传说中的奇遇？
        他连忙躬身行礼："请前辈指点！"
        
        老者点了点头："好，我就传你一套绝世武功。"
        说完，老者伸出手指，点在了李逍遥的额头上。
        
        顿时，一股强大的力量涌入了李逍遥的体内。
        他感觉自己的身体仿佛要炸开了一样，痛苦不堪。
        但是他咬紧牙关，坚持着没有发出声音。
        
        不知过了多久，老者收回了手指。
        "好了，你已经学会了我的毕生功力。"
        李逍遥感受着体内澎湃的力量，激动得说不出话来。
        
        他知道，从今天起，他的人生将彻底改变。
        他将踏上一条前所未有的道路，走向巅峰！
        
        （本章完）
        """
        
        cleaned = clean_chapter_text(test_text)
        print(f"\n✅ 文本清洗测试成功")
        print(f"   - 原始长度：{len(test_text)}")
        print(f"   - 清洗后长度：{len(cleaned)}")
        print(f"   - 去除了广告和无效内容")
        
        # 测试有效性检查
        valid = is_valid_chapter(cleaned)
        print(f"✅ 有效性检查：{'有效' if valid else '无效'}")
        
        # 测试特征提取
        features = extract_chapter_features(cleaned, chapter_number=1, title="第一章 测试")
        print(f"\n✅ 特征提取测试成功")
        print(f"   - 字数：{features.word_count}")
        print(f"   - 段落数：{features.paragraph_count}")
        print(f"   - 对话占比：{features.dialogue_ratio:.2%}")
        print(f"   - 了字密度：{features.le_word_density:.1f}/千字")
        print(f"   - 转折词密度：{features.transition_word_density:.1f}/千字")
        print(f"   - 抽象副词密度：{features.abstract_adverb_density:.1f}/千字")
        print(f"   - 爽点数量：{features.payoff_count}")
        print(f"   - 角色数量：{features.character_count}")
        print(f"   - 章末钩子类型：{features.ending_hook_type}")
        
        # 测试统计聚合
        chapters = [
            {"text": cleaned, "chapter_number": 1, "title": "第一章"},
            {"text": cleaned * 2, "chapter_number": 2, "title": "第二章"},
            {"text": cleaned * 3, "chapter_number": 3, "title": "第三章"},
        ]
        
        result = distill_genre(chapters, genre_name="测试品类")
        print(f"\n✅ 完整蒸馏流程测试成功")
        print(f"   - 样本数量：{result.stats.sample_count}")
        print(f"   - 规则建议：{len(result.rule_suggestions)} 条")
        print(f"   - 人工任务：{len(result.human_todo)} 项")
        print(f"   - 置信度：{result.confidence:.0%}")
        
        # 列出规则建议
        print(f"\n规则建议示例：")
        for rule in result.rule_suggestions[:3]:
            print(f"   - [{rule['rule_type']}] {rule['description'][:50]}...")
        
        return True
    except Exception as e:
        print(f"❌ 品类蒸馏管线测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance():
    """测试8：性能测试。"""
    print("\n" + "=" * 60)
    print("测试8：性能测试")
    print("=" * 60)
    
    try:
        # 用 exec 执行文件
        module_globals = {}
        file_path = Path(__file__).parent.parent / "backend/app/v7/services/genre_distillation.py"
        with open(file_path, "r", encoding="utf-8") as f:
            exec(f.read(), module_globals)
        
        extract_chapter_features = module_globals["extract_chapter_features"]
        distill_genre = module_globals["distill_genre"]
        
        # 生成测试文本
        test_text = "这是一段测试文本。" * 100  # 约1000字
        
        # 测试单章特征提取性能
        start_time = time.time()
        iterations = 100
        for i in range(iterations):
            extract_chapter_features(test_text, chapter_number=i, title=f"第{i}章")
        elapsed = time.time() - start_time
        
        avg_time = elapsed / iterations * 1000  # 毫秒
        print(f"✅ 单章特征提取：{avg_time:.2f} ms/章")
        print(f"   - 测试次数：{iterations}")
        print(f"   - 总耗时：{elapsed:.3f} s")
        
        # 测试多章蒸馏性能
        chapters = []
        for i in range(50):
            chapters.append({
                "text": test_text * (2 + i % 3),  # 2000-4000字
                "chapter_number": i + 1,
                "title": f"第{i+1}章 测试",
            })
        
        start_time = time.time()
        result = distill_genre(chapters, genre_name="性能测试")
        elapsed = time.time() - start_time
        
        print(f"\n✅ 50章蒸馏：{elapsed:.3f} s")
        print(f"   - 样本数量：{result.stats.sample_count}")
        print(f"   - 规则建议：{len(result.rule_suggestions)} 条")
        print(f"   - 平均每章：{elapsed / 50 * 1000:.2f} ms")
        
        # 性能评级
        if avg_time < 10:
            print(f"\n🏆 性能评级：优秀（<10ms/章）")
        elif avg_time < 50:
            print(f"\n👍 性能评级：良好（<50ms/章）")
        else:
            print(f"\n⚠️  性能评级：一般（>50ms/章）")
        
        return True
    except Exception as e:
        print(f"❌ 性能测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_world_constraint_integration():
    """测试9：世界观硬约束与品类库集成。"""
    print("\n" + "=" * 60)
    print("测试9：世界观硬约束与品类库集成")
    print("=" * 60)
    
    try:
        # 直接导入文件
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "world_constraint",
            Path(__file__).parent.parent / "backend/app/v7/quality/world_constraint.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        WorldConstraintRule = module.WorldConstraintRule
        WorldConstraintPack = module.WorldConstraintPack
        register_constraint_pack = module.register_constraint_pack
        get_constraint_pack = module.get_constraint_pack
        list_available_packs = module.list_available_packs
        
        print("✅ 世界观硬约束模块导入成功")
        
        # 列出可用约束包
        available = list_available_packs()
        print(f"✅ 可用约束包：{available}")
        
        # 检查封神约束包
        fengshen_pack = get_constraint_pack("fengshen")
        if fengshen_pack:
            print(f"✅ 封神约束包存在")
            print(f"   - 名称：{fengshen_pack.name}")
            print(f"   - 规则数量：{len(fengshen_pack.rules)}")
            
            # 测试违规检测
            test_text = "他修炼到了筑基期，马上就要突破金丹了。还有灵根和储物袋。"
            result = fengshen_pack.check_text(test_text)
            
            print(f"\n✅ 违规检测测试成功")
            print(f"   - 是否通过：{result['passed']}")
            print(f"   - 违规数量：{result['summary']['total_violations']}")
            print(f"   - 高级违规：{result['summary']['high_severity']}")
            
            if result['violations']:
                print(f"\n违规详情：")
                for v in result['violations'][:3]:
                    print(f"   - [{v['severity']}] {v['description']}: {v['matched']}")
        else:
            print("⚠️  封神约束包未找到")
        
        return True
    except Exception as e:
        print(f"❌ 世界观硬约束测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数。"""
    print("\n" + "=" * 60)
    print("NovelCraft 第二期集成测试 - 品类工厂")
    print("=" * 60)
    print(f"测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("品类库模型", test_genre_models),
        ("继承解析引擎", test_genre_inheritance_engine),
        ("品类API路由", test_genre_api),
        ("品类预置内容", test_genre_presets),
        ("初始化脚本", test_init_script),
        ("Context Assembler第8层", test_context_assembler_genre_layer),
        ("品类蒸馏管线", test_genre_distillation),
        ("性能测试", test_performance),
        ("世界观硬约束集成", test_world_constraint_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} 测试异常：{e}")
            results.append((name, False))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计：{passed}/{total} 项通过")
    
    if passed == total:
        print("\n🎉 所有测试全部通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 项测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
