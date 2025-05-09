-- client.lua
local json = require("cjson")

-- Constants
local VALID_REPLY_TYPES = {
    WORK_COMMENT = true,
    WORK_REPLY = true,
    WORK_REPLY_REPLY = true,
    POST_COMMENT = true,
    POST_REPLY = true,
    POST_REPLY_REPLY = true
}

local OK_CODE = 200

-- Singleton implementation
local function singleton(class)
    local instance
    return setmetatable({}, {
        __call = function(cls, ...)
            if not instance then
                instance = class.new(...)
            end
            return instance
        end
    })
end

-- Union class
local Union = {}
Union.__index = Union

function Union.new()
    local self = setmetatable({}, Union)
    -- Initialize components
    self.acquire = require("utils.acquire").new()
    self.cache_manager = require("utils.data").CacheManager()
    self.cache = self.cache_manager:getData()
    self.data = require("utils.data").DataManager():getData()
    self.setting = require("utils.data").SettingManager():getData()
    self.tool = require("utils.tool")
    
    -- API modules
    self.community = require("api.community")
    self.edu = require("api.edu")
    self.forum = require("api.forum")
    self.shop = require("api.shop")
    self.user = require("api.user")
    self.whale = require("api.whale")
    self.work = require("api.work")
    
    return self
end

function Union:message_report(user_id)
    -- 获取用户荣誉信息
    local response = self.user.Obtain:get_user_honor(user_id)
    -- 获取当前时间戳
    local timestamp = self.community.Obtain:get_timestamp().data
    
    -- 构造用户数据
    local user_data = {
        user_id = response.user_id,
        nickname = response.nickname,
        level = response.author_level,
        fans = response.fans_total,
        collected = response.collected_total,
        liked = response.liked_total,
        view = response.view_times,
        timestamp = timestamp
    }
    
    -- 获取缓存数据
    local before_data = self.cache_manager:getData()
    
    -- 如果缓存数据不为空，分析数据变化
    if next(before_data) then
        self:compare_datasets(
            before_data,
            user_data,
            {
                fans = "粉丝",
                collected = "被收藏",
                liked = "被赞",
                view = "浏览量"
            }
        )
    end
    
    -- 更新缓存
    self.cache_manager:update(user_data)
end

function Union:compare_datasets(before, after, metrics)
    local changes = {}
    
    for key, label in pairs(metrics) do
        local old_value = before[key] or 0
        local new_value = after[key] or 0
        local diff = new_value - old_value
        
        if diff ~= 0 then
            table.insert(changes, {
                metric = label,
                old = old_value,
                new = new_value,
                diff = diff
            })
        end
    end
    
    -- 打印变化
    if #changes > 0 then
        print("\n数据变化:")
        for _, change in ipairs(changes) do
            local sign = change.diff > 0 and "+" or ""
            print(string.format(
                "%s: %d -> %d (%s%d)",
                change.metric,
                change.old,
                change.new,
                sign,
                change.diff
            ))
        end
    end
end

function Union:get_account_status()
    return self.community.Motion:get_account_status()
end

function Union:clear_red_point(method)
    method = method or "web"
    if method ~= "web" and method ~= "nemo" then
        return false
    end
    return self.community.Motion:clear_red_point(method)
end

function Union:clear_comments(source, action_type)
    if not source or not action_type then
        return false
    end
    if source ~= "work" and source ~= "post" then
        return false
    end
    if action_type ~= "ads" and action_type ~= "duplicates" and action_type ~= "blacklist" then
        return false
    end
    return self.community.Motion:clear_comments(source, action_type)
end

-- Phone number guessing functionality
function Union:guess_phonenum(phonenum)
    -- 枚举10000个四位数
    for i = 0, 9999 do
        local guess = string.format("%04d", i)
        local test_string = tonumber(phonenum:gsub("****", guess))
        print(test_string)
        if self.user.Motion:verify_phone(test_string) then
            return test_string
        end
    end
    return nil
end

-- Create singleton instance
Union = singleton(Union)

-- Tool class (inherits from Union)
local Tool = setmetatable({}, { __index = Union })
Tool.__index = Tool

function Tool.new()
    local self = setmetatable(Union(), Tool)
    return self
end

Tool = singleton(Tool)

-- Obtain class (inherits from Union)
local Obtain = setmetatable({}, { __index = Union })
Obtain.__index = Obtain

function Obtain.new()
    local self = setmetatable(Union(), Obtain)
    return self
end

function Obtain:get_new_replies(limit, type_item)
    limit = limit or 0
    type_item = type_item or "COMMENT_REPLY"
    
    -- 验证type_item的有效性
    local valid_types = {
        LIKE_FORK = true,
        COMMENT_REPLY = true,
        SYSTEM = true
    }
    if not valid_types[type_item] then
        return {}
    end
    
    local replies = {}
    
    -- 获取初始消息计数
    local success, message_data = pcall(function()
        return self.community.Obtain:get_message_count("web")
    end)
    
    if not success or not message_data then
        print("获取消息计数失败")
        return replies
    end
    
    local total_replies = message_data[1] and message_data[1].count or 0
    
    -- 处理无新回复的情况
    if total_replies == 0 and limit == 0 then
        return replies
    end
    
    -- 设置获取数量
    local target_limit = limit > 0 and limit or total_replies
    
    -- 分页获取回复
    local function fetch_replies(page)
        local response = self.community.Obtain:get_messages({
            method = "web",
            type = type_item,
            page = page,
            limit = 20  -- API限制每页最多20条
        })
        
        if response and response.items then
            return response.items
        end
        return {}
    end
    
    -- 循环获取所有回复
    local page = 1
    while #replies < target_limit do
        local batch = fetch_replies(page)
        if #batch == 0 then
            break
        end
        
        -- 添加回复到结果列表
        for _, reply in ipairs(batch) do
            if #replies >= target_limit then
                break
            end
            table.insert(replies, reply)
        end
        
        page = page + 1
    end
    
    return replies
end

function Obtain:get_replies_batch(type_item, limit, offset)
    local response = self.community.Obtain:get_replies({
        types = type_item,
        limit = limit,
        offset = offset
    })
    
    if response and response.items then
        return response.items
    end
    return {}
end

function Obtain:process_reply_data(reply)
    -- 确保reply是有效的
    if not reply then
        return nil
    end
    
    -- 提取基础信息
    local processed = {
        id = reply.id,
        type = reply.type,
        content = reply.content,
        created_at = reply.created_at
    }
    
    -- 处理发送者信息
    if reply.sender then
        processed.sender = {
            id = reply.sender.id,
            nickname = reply.sender.nickname,
            avatar = reply.sender.avatar
        }
    end
    
    -- 处理目标信息
    if reply.target then
        processed.target = {
            id = reply.target.id,
            type = reply.target.type
        }
        
        -- 如果目标是作品，添加作品信息
        if reply.target.type == "WORK" and reply.target.work then
            processed.target.work = {
                id = reply.target.work.id,
                name = reply.target.work.name
            }
        end
    end
    
    return processed
end

function Obtain:get_comments_detail_new(com_id, source, method, max_limit)
    -- 参数验证
    local valid_sources = { work = true, post = true, shop = true }
    local valid_methods = { user_id = true, comments = true, comment_id = true }
    
    if not valid_sources[source] or not valid_methods[method] then
        return {}
    end
    
    method = method or "user_id"
    max_limit = max_limit or 200
    
    local comments = {}
    local page = 1
    local limit = 20 -- 每页评论数
    
    while true do
        -- 根据source选择不同的API
        local response
        if source == "work" then
            response = self.work.Obtain:get_work_comments(com_id, page, limit)
        elseif source == "post" then
            response = self.forum.Obtain:get_post_comments(com_id, page, limit)
        elseif source == "shop" then
            response = self.shop.Obtain:get_shop_comments(com_id, page, limit)
        end
        
        if not response or not response.items or #response.items == 0 then
            break
        end
        
        -- 处理评论数据
        for _, comment in ipairs(response.items) do
            if #comments >= max_limit then
                break
            end
            
            if method == "user_id" then
                table.insert(comments, comment.user_id)
            elseif method == "comment_id" then
                table.insert(comments, comment.id)
            elseif method == "comments" then
                table.insert(comments, {
                    id = comment.id,
                    user_id = comment.user_id,
                    nickname = comment.nickname,
                    content = comment.content,
                    created_at = comment.created_at,
                    replies = comment.replies or {}
                })
            end
        end
        
        if #comments >= max_limit then
            break
        end
        
        page = page + 1
    end
    
    return comments
end

function Obtain:get_reply_details(reply_id)
    local response = self.community.Obtain:get_reply_details(reply_id)
    if response then
        return self:process_reply_data(response)
    end
    return nil
end

function Obtain:get_work_reply_details(work_id)
    local response = self.work.Obtain:get_work_comments(work_id)
    if response and response.items then
        local details = {}
        for _, item in ipairs(response.items) do
            table.insert(details, self:process_reply_data(item))
        end
        return details
    end
    return {}
end

-- Add DataProcessor as a local table inside Obtain class
local function deduplicate(list)
    local seen = {}
    local result = {}
    
    for _, value in ipairs(list) do
        if not seen[value] then
            seen[value] = true
            table.insert(result, value)
        end
    end
    
    return result
end

function Obtain:generate_replies(comment, source)
    local replies = {}
    
    if source == "post" then
        -- 处理帖子回复
        local response = self.forum.Obtain:get_reply_post_comments(comment.id)
        if response and response.items then
            return response.items
        end
    else
        -- 处理其他类型回复
        if comment.replies and comment.replies.items then
            return comment.replies.items
        end
    end
    
    return replies
end

function Obtain:process_comments_by_type(comments, source, method)
    if method == "user_id" then
        local user_ids = {}
        for _, comment in ipairs(comments) do
            if comment.user and comment.user.id then
                table.insert(user_ids, comment.user.id)
            end
            
            -- 处理回复中的用户ID
            local replies = self:generate_replies(comment, source)
            for _, reply in ipairs(replies) do
                local reply_user_id = self:extract_reply_user(reply)
                if reply_user_id then
                    table.insert(user_ids, reply_user_id)
                end
            end
        end
        return deduplicate(user_ids)
        
    elseif method == "comment_id" then
        local comment_ids = {}
        for _, comment in ipairs(comments) do
            if comment.id then
                table.insert(comment_ids, tostring(comment.id))
            end
            
            -- 处理回复中的评论ID
            local replies = self:generate_replies(comment, source)
            for _, reply in ipairs(replies) do
                if reply.id then
                    table.insert(comment_ids, 
                        string.format("%s.%s", comment.id, reply.id))
                end
            end
        end
        return deduplicate(comment_ids)
        
    else -- method == "comments"
        return self:process_comments(comments, method)
    end
end

function Obtain:process_detailed_comments(comments, user_field)
    local detailed = {}
    
    for _, item in ipairs(comments) do
        if item.user and item.id then
            local comment_data = {
                user_id = item.user.id,
                nickname = item.user.nickname,
                id = item.id,
                content = item.content,
                created_at = item.created_at,
                is_top = item.is_top or false,
                replies = {}
            }
            
            -- 处理回复
            local replies = self:generate_replies(item, item.source)
            for _, r_item in ipairs(replies) do
                if r_item.id then
                    table.insert(comment_data.replies, {
                        id = r_item.id,
                        content = r_item.content,
                        created_at = r_item.created_at,
                        user_id = self:extract_reply_user(r_item),
                        nickname = r_item[user_field] and r_item[user_field].nickname
                    })
                end
            end
            
            table.insert(detailed, comment_data)
        end
    end
    
    return detailed
end

function Obtain:get_structured_comments(com_id, source, method, max_limit)
    max_limit = max_limit or 200
    
    -- 定义数据源配置
    local source_config = {
        work = {
            get_func = function(id) 
                return self.work.Obtain:get_work_comments(id, 1, max_limit)
            end,
            id_key = "work_id",
            user_field = "reply_user"
        },
        post = {
            get_func = function(id)
                return self.forum.Obtain:get_post_replies_posts(id, max_limit)
            end,
            id_key = "ids",
            user_field = "user"
        },
        shop = {
            get_func = function(id)
                return self.shop.Obtain:get_shop_discussion(id, max_limit)
            end,
            id_key = "shop_id",
            user_field = "reply_user"
        }
    }
    
    -- 验证来源有效性
    if not source_config[source] then
        error(string.format("不支持的来源类型: %s", source))
    end
    
    -- 获取评论数据
    local config = source_config[source]
    local comments = config.get_func(com_id)
    
    if not comments or not comments.items then
        return {}
    end
    
    -- 根据方法处理数据
    return self:process_comments_by_type(comments.items, source, method)
end

-- Helper functions for comment processing
local function extract_reply_user(reply)
    if not reply then return nil end
    
    -- Handle different reply structures
    if reply.reply_user then
        return reply.reply_user.id
    elseif reply.user then
        return reply.user.id
    elseif reply.user_id then
        return reply.user_id
    end
    return nil
end

local function extract_comment_id(comment)
    if not comment then return nil end
    return comment.id
end

local function extract_comment_data(comment)
    if not comment then return nil end
    
    local data = {
        id = comment.id,
        content = comment.content,
        created_at = comment.created_at,
        updated_at = comment.updated_at,
        replies = {}
    }
    
    -- Add user info
    if comment.user then
        data.user = {
            id = comment.user.id,
            nickname = comment.user.nickname,
            avatar = comment.user.avatar
        }
    end
    
    -- Process replies if they exist
    if comment.replies then
        for _, reply in ipairs(comment.replies) do
            table.insert(data.replies, extract_comment_data(reply))
        end
    end
    
    return data
end

function Obtain:process_comments(comments, method)
    local result = {}
    
    for _, comment in ipairs(comments) do
        if method == "user_id" then
            local user_id = extract_reply_user(comment)
            if user_id then
                table.insert(result, user_id)
            end
        elseif method == "comment_id" then
            local comment_id = extract_comment_id(comment)
            if comment_id then
                table.insert(result, comment_id)
            end
        elseif method == "comments" then
            local comment_data = extract_comment_data(comment)
            if comment_data then
                table.insert(result, comment_data)
            end
        end
    end
    
    return result
end

Obtain = singleton(Obtain)

-- Math Utils
local MathUtils = {}

function MathUtils.clamp(value, min, max)
    return math.min(math.max(value, min), max)
end

-- DataProcessor
local DataProcessor = {}

function DataProcessor.deduplicate(list)
    local seen = {}
    local result = {}
    
    for _, value in ipairs(list) do
        if not seen[value] then
            seen[value] = true
            table.insert(result, value)
        end
    end
    
    return result
end

function DataProcessor.generate_replies(self, comment, source)
    local replies = {}
    
    if source == "post" then
        -- 处理帖子回复
        local response = self.forum.Obtain:get_reply_post_comments(comment.id)
        if response and response.items then
            return response.items
        end
    else
        -- 处理其他类型回复
        if comment.replies and comment.replies.items then
            return comment.replies.items
        end
    end
    
    return replies
end

-- Motion class (inherits from Union)
local Motion = setmetatable({}, { __index = Union })
Motion.__index = Motion

function Motion.new()
    local self = setmetatable(Union(), Motion)
    -- 配置不同来源的参数
    self.SOURCE_CONFIG = {
        work = {
            items = function()
                return self.user.Obtain:get_user_works_web(self.data.ACCOUNT_DATA.id)
            end,
            get_comments = function(id)
                return Obtain():get_comments_detail_new(id, "work", "comments")
            end,
            delete = function(id, comment_id)
                return self.work.Motion:del_comment_work(id, comment_id)
            end,
            title_key = "work_name"
        },
        post = {
            items = function()
                return self.forum.Obtain:get_post_mine_all("created")
            end,
            get_comments = function(id)
                return Obtain():get_comments_detail_new(id, "post", "comments")
            end,
            delete = function(id, comment_id, opts)
                local comment_type = opts and opts.is_reply and "comments" or "replies"
                return self.forum.Motion:delete_comment_post_reply(comment_id, comment_type)
            end,
            title_key = "title"
        }
    }
    return self
end

local function contains_blacklisted_words(text, blacklist)
    if not text or not blacklist then return false end
    text = string.lower(text)
    for _, word in ipairs(blacklist) do
        if string.find(text, string.lower(word)) then
            return true
        end
    end
    return false
end

local function is_advertisement(text)
    if not text then return false end
    local ad_patterns = {
        "点击.*链接",
        "复制.*链接",
        "加.*微信",
        "加.*qq",
        "联系方式",
        "私聊",
        "代肝",
        "工作室",
        "有偿",
        "接单"
    }
    text = string.lower(text)
    for _, pattern in ipairs(ad_patterns) do
        if string.find(text, pattern) then
            return true
        end
    end
    return false
end

local function is_duplicate_comment(comments, current_comment)
    if not comments or not current_comment then return false end
    local count = 0
    for _, comment in ipairs(comments) do
        if comment.content == current_comment.content then
            count = count + 1
            if count > 1 then
                return true
            end
        end
    end
    return false
end

function Motion:clear_comments(source, action_type)
    -- 验证参数
    if not self.SOURCE_CONFIG[source] then
        return false
    end
    
    local valid_actions = { ads = true, duplicates = true, blacklist = true }
    if not valid_actions[action_type] then
        return false
    end
    
    -- 获取所有内容项
    local items = self.SOURCE_CONFIG[source].items()
    if not items then return false end
    
    -- 处理每个内容项
    for _, item in ipairs(items) do
        local comments = self.SOURCE_CONFIG[source].get_comments(item.id)
        if comments then
            for _, comment in ipairs(comments) do
                local should_delete = false
                
                if action_type == "ads" then
                    should_delete = is_advertisement(comment.content)
                elseif action_type == "duplicates" then
                    should_delete = is_duplicate_comment(comments, comment)
                elseif action_type == "blacklist" then
                    should_delete = contains_blacklisted_words(comment.content, self.setting.REPLY.BLACK_LIST)
                end
                
                if should_delete then
                    -- 删除评论
                    self.SOURCE_CONFIG[source].delete(item.id, comment.id, {
                        is_reply = comment.is_reply
                    })
                    -- 添加延迟避免请求过快
                    os.execute("ping -n 2 127.0.0.1 > nul")
                end
                
                -- 处理评论的回复
                if comment.replies then
                    for _, reply in ipairs(comment.replies) do
                        local should_delete_reply = false
                        
                        if action_type == "ads" then
                            should_delete_reply = is_advertisement(reply.content)
                        elseif action_type == "duplicates" then
                            should_delete_reply = is_duplicate_comment(comment.replies, reply)
                        elseif action_type == "blacklist" then
                            should_delete_reply = contains_blacklisted_words(reply.content, self.setting.REPLY.BLACK_LIST)
                        end
                        
                        if should_delete_reply then
                            self.SOURCE_CONFIG[source].delete(item.id, reply.id, {
                                is_reply = true
                            })
                            os.execute("ping -n 2 127.0.0.1 > nul")
                        end
                    end
                end
            end
        end
    end
    
    return true
end

-- Index class (Singleton)
local Index = setmetatable({}, { __index = Union })
Index.__index = Index

local index_instance = nil

function Index.new()
    if index_instance then
        return index_instance
    end
    
    local self = setmetatable(Union.new(), Index)
    
    -- 颜色配置
    self.COLOR_DATA = "\027[38;5;228m"    -- 月光黄-数据
    self.COLOR_LINK = "\027[4;38;5;183m"  -- 薰衣草紫带下划线-链接
    self.COLOR_RESET = "\027[0m"          -- 样式重置
    self.COLOR_SLOGAN = "\027[38;5;80m"   -- 湖水青-标语
    self.COLOR_TITLE = "\027[38;5;75m"    -- 晴空蓝-标题
    self.COLOR_VERSION = "\027[38;5;114m" -- 新芽绿-版本号
    
    index_instance = self
    return self
end

function Index:index()
    -- 打印slogan
    print(string.format("\n%s%s%s", 
        self.COLOR_SLOGAN, 
        self.setting.PROGRAM.SLOGAN, 
        self.COLOR_RESET))
        
    -- 打印版本号
    print(string.format("%s版本号: %s%s",
        self.COLOR_VERSION,
        self.setting.PROGRAM.VERSION,
        self.COLOR_RESET))
    
    -- 打印一言
    local title = string.rep("*", 22) .. " 一言 " .. string.rep("*", 22)
    print(string.format("\n%s%s%s", self.COLOR_TITLE, title, self.COLOR_RESET))
    
    local response = self.acquire:get("https://lty.vc/lyric")
    if response and response.text then
        print(string.format("%s%s%s", self.COLOR_SLOGAN, response.text, self.COLOR_RESET))
    end
    
    -- 打印公告
    title = string.rep("*", 22) .. " 公告 " .. string.rep("*", 22)
    print(string.format("\n%s%s%s", self.COLOR_TITLE, title, self.COLOR_RESET))
    
    -- 打印链接
    print(string.format("%s编程猫社区行为守则 https://shequ.codemao.cn/community/1619098%s",
        self.COLOR_LINK, self.COLOR_RESET))
    print(string.format("%s2025编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855%s",
        self.COLOR_LINK, self.COLOR_RESET))
    
    -- 打印数据
    local data_title = string.rep("*", 22) .. " 数据 " .. string.rep("*", 22)
    print(string.format("\n%s%s%s", self.COLOR_DATA, data_title, self.COLOR_RESET))
    
    -- 调用数据报告
    Tool():message_report(self.data.ACCOUNT_DATA.id)
    
    -- 分隔线
    print(string.format("%s%s%s\n", 
        self.COLOR_TITLE, 
        string.rep("*", 50), 
        self.COLOR_RESET))
end

Index = singleton(Index)

-- Export
return {
    Union = Union,
    Tool = Tool,
    Obtain = Obtain,
    Motion = Motion,
    Index = Index,
    MathUtils = MathUtils,
    DataProcessor = DataProcessor,
    VALID_REPLY_TYPES = VALID_REPLY_TYPES,
    OK_CODE = OK_CODE
}
