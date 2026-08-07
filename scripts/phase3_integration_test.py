#!/usr/bin/env python3
"""
第三期集成测试 — 智能增强阶段（阶段15-21）

测试内容：
1. 情感弧线映射
2. 读者留存预测器
3. 子品类自动发现
4. 系列模型导入（需Docker环境）
5. 分支生成器 API 导入（需Docker环境）
6. 性能测试

说明：
- 标记为"需Docker环境"的测试需要在完整的后端环境中运行
- 本地环境可测试纯功能模块（情感弧线、留存预测、子品类发现等）
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# 添加模块路径（直接导入，避免触发 app.v7 的 __init__.py）
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "app" / "v7" / "quality"))
sys.path.insert(0, str(ROOT / "backend" / "app" / "v7" / "services"))


def test_emotional_arc():
    """测试1：情感弧线映射"""
    print("\n" + "=" * 60)
    print("测试1：情感弧线映射")
    print("=" * 60)

    try:
        from emotional_arc import (
            analyze_chapter_emotion,
            analyze_emotional_arc,
            get_emotion_summary,
            get_arc_summary,
        )
        print("✅ 模块导入成功")
    except Exception as e:
        print(f"❌ 模块导入失败：{e}")
        return False

    # 测试单章情感分析
    test_text = """
    林辰看着眼前的敌人，心中充满了愤怒和不甘。他握紧了拳头，指甲深深嵌入掌心。
    "我绝不会认输！"他怒吼一声，全身爆发出强大的力量。
    敌人被这突如其来的力量震住了，脸上露出了恐惧的表情。
    林辰乘胜追击，一招制敌，终于取得了胜利！
    他站在废墟之上，仰天长笑，心中充满了喜悦和自豪。
    但是，他知道，这只是开始，更大的挑战还在后面等着他。
    """

    try:
        start_time = time.time()
        result = analyze_chapter_emotion(test_text)
        elapsed = (time.time() - start_time) * 1000

        print(f"\n单章分析结果：")
        print(f"  情感强度评分：{result.score:.1f}/10")
        print(f"  情感价：{result.valence:.2f}")
        print(f"  唤醒度：{result.arousal:.2f}")
        print(f"  主导情绪：{result.emotion_type}")
        print(f"  积极词数量：{result.positive_count}")
        print(f"  消极词数量：{result.negative_count}")
        print(f"  总字数：{result.word_count}")
        print(f"  耗时：{elapsed:.2f} ms")

        if result.score > 0 and result.word_count > 0:
            print("✅ 单章分析正常")
        else:
            print("❌ 单章分析结果异常")
            return False
    except Exception as e:
        print(f"❌ 单章分析失败：{e}")
        return False

    # 测试多章情感弧线
    chapters = [
        "第一章：主角出场，平平淡淡，生活平静。",
        "第二章：遇到小麻烦，有点紧张，但很快解决了。",
        "第三章：发现神秘力量，兴奋激动，开始修炼。",
        "第四章：遇到第一个敌人，战斗激烈，险胜。",
        "第五章：获得奖励，实力提升，非常开心。",
        "第六章：遇到更大的危机，陷入困境，感到绝望。",
        "第七章：低谷期，迷茫痛苦，不知道该怎么办。",
        "第八章：重新振作，找到突破口，燃起希望。",
        "第九章：再次战斗，更加激烈，最终胜利。",
        "第十章：巅峰时刻，实力大增，万众瞩目！",
    ]

    try:
        start_time = time.time()
        arc_result = analyze_emotional_arc(chapters)
        elapsed = (time.time() - start_time) * 1000

        print(f"\n多章弧线分析结果：")
        print(f"  章节数量：{arc_result.chapter_count}")
        print(f"  整体情感强度：{arc_result.overall_score:.1f}/10")
        print(f"  弧线类型：{arc_result.arc_type}")
        print(f"  最高峰章节：第{arc_result.peak_chapter}章")
        print(f"  最低谷章节：第{arc_result.valley_chapter}章")
        print(f"  波动幅度：{arc_result.volatility:.2f}")
        print(f"  异常数量：{len(arc_result.anomalies)}")
        print(f"  改进建议数量：{len(arc_result.suggestions)}")
        print(f"  耗时：{elapsed:.2f} ms")

        print(f"\n每章评分：")
        for i, score in enumerate(arc_result.scores):
            bar = "█" * int(score)
            print(f"  第{i+1}章：{score:.1f} {bar}")

        if arc_result.chapter_count == 10 and len(arc_result.scores) == 10:
            print("✅ 多章弧线分析正常")
        else:
            print("❌ 多章弧线分析结果异常")
            return False
    except Exception as e:
        print(f"❌ 多章弧线分析失败：{e}")
        return False

    # 测试摘要函数
    try:
        emotion_summary = get_emotion_summary(result)
        arc_summary = get_arc_summary(arc_result)
        print(f"\n摘要函数测试：")
        print(f"  情感摘要长度：{len(emotion_summary)} 字符")
        print(f"  弧线摘要长度：{len(arc_summary)} 字符")
        print("✅ 摘要函数正常")
    except Exception as e:
        print(f"❌ 摘要函数失败：{e}")
        return False

    return True


def test_retention_predictor():
    """测试2：读者留存预测器"""
    print("\n" + "=" * 60)
    print("测试2：读者留存预测器")
    print("=" * 60)

    try:
        from retention_predictor import (
            predict_retention,
            get_feature_list,
            get_baseline,
            get_retention_level,
            compare_with_baseline,
        )
        print("✅ 模块导入成功")
    except Exception as e:
        print(f"❌ 模块导入失败：{e}")
        return False

    # 测试特征列表
    try:
        features = get_feature_list()
        print(f"\n特征列表：")
        print(f"  总特征数：{len(features)}")
        categories = set(f["category"] for f in features)
        print(f"  分类数：{len(categories)}")
        print(f"  分类：{', '.join(sorted(categories))}")

        if len(features) >= 30:
            print("✅ 特征列表正常")
        else:
            print("❌ 特征数量不足")
            return False
    except Exception as e:
        print(f"❌ 特征列表获取失败：{e}")
        return False

    # 测试基准值
    try:
        for platform in ["fanqie", "qidian", "jjwxc", "default"]:
            baseline = get_baseline(platform)
            print(f"\n{platform} 基准值：")
            print(f"  特征数：{len(baseline)}")
            # 显示前5个特征
            for i, (key, value) in enumerate(list(baseline.items())[:5]):
                print(f"    {key}: {value}")

        print("✅ 基准值正常")
    except Exception as e:
        print(f"❌ 基准值获取失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试留存预测
    try:
        # 直接用基准值来测试预测功能
        baseline = get_baseline("fanqie")
        test_features = dict(baseline)

        start_time = time.time()
        result = predict_retention(test_features, platform="fanqie")
        elapsed = (time.time() - start_time) * 1000

        print(f"\n预测结果（基准样本）：")
        print(f"  预测留存率：{result.predicted_retention:.1f}%")
        print(f"  基础留存率：{result.base_retention:.1f}%")
        print(f"  总调整量：{result.total_adjustment:+.1f}%")
        print(f"  留存等级：{get_retention_level(result.predicted_retention)}")
        print(f"  拖累因素数：{len(result.top_drag_factors)}")
        print(f"  加分因素数：{len(result.top_boost_factors)}")
        print(f"  分类得分数：{len(result.category_scores)}")
        print(f"  建议数：{len(result.suggestions)}")
        print(f"  置信度：{result.confidence:.2f}")
        print(f"  耗时：{elapsed:.2f} ms")

        if result.predicted_retention > 0:
            print("✅ 预测结果正常")
        else:
            print("❌ 预测结果异常")
            return False
    except Exception as e:
        print(f"❌ 留存预测失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试留存等级
    try:
        levels = [95, 85, 75, 65, 55]
        print(f"\n留存等级测试：")
        for score in levels:
            level = get_retention_level(score)
            print(f"  {score}% → {level}")
        print("✅ 留存等级正常")
    except Exception as e:
        print(f"❌ 留存等级失败：{e}")
        return False

    return True


def test_subgenre_discovery():
    """测试3：子品类自动发现"""
    print("\n" + "=" * 60)
    print("测试3：子品类自动发现")
    print("=" * 60)

    try:
        from subgenre_discovery import (
            kmeans_clustering,
            find_optimal_k,
            discover_subgenres,
            get_cluster_summary,
            assign_to_cluster,
            calculate_silhouette_score,
            normalize_features,
        )
        print("✅ 模块导入成功")
    except Exception as e:
        print(f"❌ 模块导入失败：{e}")
        return False

    # 生成测试数据
    import random
    random.seed(42)

    # 创建 3 个聚类的样本数据
    n_samples = 30
    n_features = 5
    samples = []

    # 聚类1：高爽点密度、快节奏
    for i in range(10):
        samples.append([
            8 + random.gauss(0, 0.5),  # 爽点密度
            9 + random.gauss(0, 0.5),  # 节奏
            7 + random.gauss(0, 0.5),  # 冲突
            6 + random.gauss(0, 0.5),  # 人物
            8 + random.gauss(0, 0.5),  # 对话占比
        ])

    # 聚类2：慢节奏、深度设定
    for i in range(10):
        samples.append([
            4 + random.gauss(0, 0.5),  # 爽点密度
            3 + random.gauss(0, 0.5),  # 节奏
            5 + random.gauss(0, 0.5),  # 冲突
            8 + random.gauss(0, 0.5),  # 人物
            4 + random.gauss(0, 0.5),  # 对话占比
        ])

    # 聚类3：中等水平
    for i in range(10):
        samples.append([
            6 + random.gauss(0, 0.5),  # 爽点密度
            6 + random.gauss(0, 0.5),  # 节奏
            6 + random.gauss(0, 0.5),  # 冲突
            6 + random.gauss(0, 0.5),  # 人物
            6 + random.gauss(0, 0.5),  # 对话占比
        ])

    feature_names = ["payoff_density", "pacing", "conflict", "character", "dialogue_ratio"]

    # 测试归一化
    try:
        normalized, params = normalize_features(samples, method="minmax")
        print(f"\n归一化测试：")
        print(f"  原始数据形状：{len(samples)} x {len(samples[0])}")
        print(f"  归一化后形状：{len(normalized)} x {len(normalized[0])}")
        print(f"  最小值：{min(min(row) for row in normalized):.2f}")
        print(f"  最大值：{max(max(row) for row in normalized):.2f}")
        print("✅ 归一化正常")
    except Exception as e:
        print(f"❌ 归一化失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试 K-Means 聚类
    try:
        start_time = time.time()
        clusters, centers, inertia, iterations, converged = kmeans_clustering(
            normalized, k=3, max_iterations=100
        )
        elapsed = (time.time() - start_time) * 1000

        print(f"\nK-Means 聚类结果：")
        print(f"  聚类数：{len(centers)}")
        print(f"  迭代次数：{iterations}")
        print(f"  是否收敛：{converged}")
        print(f"  Inertia：{inertia:.4f}")
        print(f"  耗时：{elapsed:.2f} ms")

        # 统计每个聚类的样本数
        cluster_counts = {}
        for c in clusters:
            cluster_counts[c] = cluster_counts.get(c, 0) + 1
        print(f"  各聚类样本数：{cluster_counts}")

        if converged and len(centers) == 3:
            print("✅ K-Means 聚类正常")
        else:
            print("❌ K-Means 聚类异常")
            return False
    except Exception as e:
        print(f"❌ K-Means 聚类失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试肘部法则
    try:
        start_time = time.time()
        optimal_k, inertias, derivatives = find_optimal_k(
            normalized, min_k=2, max_k=6
        )
        elapsed = (time.time() - start_time) * 1000

        print(f"\n肘部法则结果：")
        print(f"  最优 K 值：{optimal_k}")
        print(f"  各 K 值 inertia：")
        for k, inertia in enumerate(inertias, start=2):
            print(f"    K={k}: {inertia:.4f}")
        print(f"  耗时：{elapsed:.2f} ms")
        print("✅ 肘部法则正常")
    except Exception as e:
        print(f"❌ 肘部法则失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试子品类发现
    try:
        start_time = time.time()
        result = discover_subgenres(
            samples,
            feature_names=feature_names,
            k=3,
        )
        elapsed = (time.time() - start_time) * 1000

        print(f"\n子品类发现结果：")
        print(f"  聚类数：{result.k}")
        print(f"  总样本数：{result.total_samples}")
        print(f"  迭代次数：{result.iterations}")
        print(f"  是否收敛：{result.converged}")
        print(f"  Inertia：{result.inertia:.4f}")
        print(f"  轮廓系数：{result.silhouette_score:.4f}")
        print(f"  耗时：{elapsed:.2f} ms")

        print(f"\n各子品类详情：")
        for cluster in result.clusters:
            print(f"\n  子品类 {cluster.cluster_id}：{cluster.name}")
            print(f"    描述：{cluster.description}")
            print(f"    样本数：{cluster.sample_count}")
            print(f"    代表作品数：{len(cluster.representative_samples)}")
            print(f"    特征重要性前3：")
            for feat, imp in sorted(
                cluster.feature_importance.items(), key=lambda x: abs(x[1]), reverse=True
            )[:3]:
                direction = "↑" if imp > 0 else "↓"
                print(f"      {feat}: {imp:+.2f} {direction}")

        if len(result.clusters) == 3:
            print("✅ 子品类发现正常")
        else:
            print("❌ 子品类发现异常")
            return False
    except Exception as e:
        print(f"❌ 子品类发现失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试新样本分配
    try:
        new_sample = [7.5, 8.5, 6.5, 6.0, 7.5]
        cluster_id, distance = assign_to_cluster(new_sample, result)
        print(f"\n新样本分配测试：")
        print(f"  新样本：{new_sample}")
        print(f"  分配到聚类：{cluster_id}")
        print(f"  距离中心：{distance:.4f}")
        print("✅ 新样本分配正常")
    except Exception as e:
        print(f"❌ 新样本分配失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_series_models():
    """测试4：系列模型导入"""
    print("\n" + "=" * 60)
    print("测试4：系列模型导入")
    print("=" * 60)

    try:
        from app.v7.models.series import Series, SeriesMember, SeriesKnowledge
        print("✅ 系列模型导入成功")
        print(f"  Series 表名：{Series.__tablename__}")
        print(f"  SeriesMember 表名：{SeriesMember.__tablename__}")
        print(f"  SeriesKnowledge 表名：{SeriesKnowledge.__tablename__}")
    except Exception as e:
        print(f"❌ 系列模型导入失败：{e}")
        return False

    return True


def test_branch_generator_api():
    """测试5：分支生成器 API 导入"""
    print("\n" + "=" * 60)
    print("测试5：分支生成器 API 导入")
    print("=" * 60)

    try:
        from app.v7.api.branch_generator import router
        print("✅ 分支生成器 API 导入成功")
        print(f"  路由前缀：{router.prefix}")
        print(f"  路由数量：{len(router.routes)}")
    except Exception as e:
        print(f"❌ 分支生成器 API 导入失败：{e}")
        return False

    return True


def test_performance():
    """测试6：性能测试"""
    print("\n" + "=" * 60)
    print("测试6：性能测试")
    print("=" * 60)

    from emotional_arc import analyze_chapter_emotion
    from retention_predictor import predict_retention, get_baseline

    # 生成测试文本
    test_text = "这是一段测试文本。" * 100  # 约 800 字

    # 情感分析性能
    times = []
    for _ in range(10):
        start = time.time()
        analyze_chapter_emotion(test_text)
        times.append((time.time() - start) * 1000)

    avg_time = sum(times) / len(times)
    print(f"\n情感分析性能（10次平均）：")
    print(f"  平均耗时：{avg_time:.2f} ms/章")
    print(f"  最快：{min(times):.2f} ms")
    print(f"  最慢：{max(times):.2f} ms")

    if avg_time < 10:
        print("✅ 情感分析性能优秀（< 10ms/章）")
    elif avg_time < 50:
        print("✅ 情感分析性能良好（< 50ms/章）")
    else:
        print("⚠️  情感分析性能一般（>= 50ms/章）")

    # 留存预测性能
    baseline = get_baseline("fanqie")
    test_features = baseline

    times = []
    for _ in range(100):
        start = time.time()
        predict_retention(test_features, platform="fanqie")
        times.append((time.time() - start) * 1000)

    avg_time = sum(times) / len(times)
    print(f"\n留存预测性能（100次平均）：")
    print(f"  平均耗时：{avg_time:.3f} ms/次")
    print(f"  最快：{min(times):.3f} ms")
    print(f"  最慢：{max(times):.3f} ms")

    if avg_time < 1:
        print("✅ 留存预测性能优秀（< 1ms/次）")
    elif avg_time < 10:
        print("✅ 留存预测性能良好（< 10ms/次）")
    else:
        print("⚠️  留存预测性能一般（>= 10ms/次）")

    return True


def main():
    """主函数"""
    print("=" * 60)
    print("NovelCraft 第三期集成测试")
    print("智能增强阶段（阶段15-21）")
    print("=" * 60)

    results = {}

    # 运行所有测试
    tests = [
        ("情感弧线映射", test_emotional_arc),
        ("读者留存预测器", test_retention_predictor),
        ("子品类自动发现", test_subgenre_discovery),
        ("系列模型导入", test_series_models),
        ("分支生成器API导入", test_branch_generator_api),
        ("性能测试", test_performance),
    ]

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ {name} 测试异常：{e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}：{status}")

    print(f"\n总计：{passed}/{total} 项通过")

    if passed == total:
        print("\n🎉 所有测试全部通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 项测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
