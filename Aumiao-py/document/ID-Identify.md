四个核心 ID 详解

1. business_id (业务 ID)
   作用: 顶层标识, 确定回复的 "主战场"
   来源:
   对于帖子: 帖子 ID
   对于作品: 作品 ID
   特点: 所有回复都归属于某个 business_id
   示例:business_id=123 → 在帖子 / 作品 123 下操作
2. target_id (目标 ID)
   作用: 要直接回复的对象 ID
   规则:
   回复一级评论时:target_id = 评论 ID
   回复二级回复时:target_id = 被回复的回复 ID
   示例:
   直接回复评论 100:target_id=100
   回复别人的回复 200:target_id=200
3. parent_id (父 ID)
   作用: 定位回复的层级位置
   规则:
   回复一级评论:parent_id = 0
   回复二级回复:parent_id = 被回复的回复的父 ID
   示例:
   在一级评论下回复:parent_id=0
   在评论 100 的回复 200 下回复:parent_id=100
4. reply_id (通知 ID)
   作用: 系统通知的唯一标识, 用于去重追踪
   特点:
   每个通知都有唯一的 reply_id
   防止重复处理同一通知
   格式如:"notif_xxx"
   使用场景速查表
   场景 business_id target_id parent_id 说明
   回复帖子的一级评论 帖子 ID 评论 ID 0 最基础的回复
   回复作品的一级评论 作品 ID 评论 ID 0 作品评论回复
   回复评论的回复 帖子 / 作品 ID 被回复的回复 ID 被回复的父 ID 嵌套回复
