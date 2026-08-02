package com.hmdp.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.hmdp.dto.Result;
import com.hmdp.dto.UserDTO;
import com.hmdp.entity.BlogComments;
import com.hmdp.service.IBlogCommentsService;
import com.hmdp.utils.SystemConstants;
import com.hmdp.utils.UserHolder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * 博客评论控制器
 *
 * 【八股：RESTful API 设计】
 * POST   /blog-comments          — 发布评论（创建资源）
 * GET    /blog-comments/blog/{id} — 查询某篇博客的评论列表（分页）
 * DELETE /blog-comments/{id}      — 删除自己的评论
 * PUT    /blog-comments/like/{id} — 点赞评论
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Slf4j
@RestController
@RequestMapping("/blog-comments")
public class BlogCommentsController {

    @Resource
    private IBlogCommentsService blogCommentsService;

    /**
     * 发布评论（支持一级评论和回复）
     *
     * @param comment 评论内容（blogId必填，parentId=0表示一级评论，answerId=被回复的评论id）
     * @return 评论ID
     */
    @PostMapping
    public Result saveComment(@RequestBody BlogComments comment) {
        UserDTO user = UserHolder.getUser();
        comment.setUserId(user.getId());
        blogCommentsService.save(comment);
        return Result.ok(comment.getId());
    }

    /**
     * 查询某篇博客的评论（分页，按时间倒序）
     *
     * @param blogId  博客ID
     * @param current 当前页码，默认1
     * @return 分页评论数据
     */
    @GetMapping("/blog/{blogId}")
    public Result queryCommentsByBlog(
            @PathVariable("blogId") Long blogId,
            @RequestParam(value = "current", defaultValue = "1") Integer current) {
        Page<BlogComments> page = blogCommentsService.query()
                .eq("blog_id", blogId)
                .orderByDesc("create_time")
                .page(new Page<>(current, SystemConstants.MAX_PAGE_SIZE));
        return Result.ok(page.getRecords());
    }

    /**
     * 删除评论（只能删除自己的评论）
     *
     * @param id 评论ID
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public Result deleteComment(@PathVariable("id") Long id) {
        BlogComments comment = blogCommentsService.getById(id);
        if (comment == null) {
            return Result.fail("评论不存在");
        }
        Long userId = UserHolder.getUser().getId();
        if (!comment.getUserId().equals(userId)) {
            return Result.fail("只能删除自己的评论");
        }
        blogCommentsService.removeById(id);
        return Result.ok();
    }

    /**
     * 点赞评论
     *
     * @param id 评论ID
     * @return 操作结果
     */
    @PutMapping("/like/{id}")
    public Result likeComment(@PathVariable("id") Long id) {
        BlogComments comment = blogCommentsService.getById(id);
        if (comment == null) {
            return Result.fail("评论不存在");
        }
        blogCommentsService.update()
                .setSql("liked = liked + 1")
                .eq("id", id)
                .update();
        return Result.ok();
    }
}
