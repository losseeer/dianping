package com.hmdp.interceptor;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.StrUtil;
import com.hmdp.dto.UserDTO;
import com.hmdp.entity.User;
import com.hmdp.utils.RedisConstants;
import com.hmdp.utils.UserHolder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.ModelAndView;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Token刷新拦截器（第一层拦截器，order=0）
 *
 * 【八股：为什么需要两层拦截器？】
 *
 * 只有一层登录拦截器的问题：
 * - 登录拦截器只拦截需要登录的路径
 * - 用户访问不需要登录的路径（比如浏览商铺）时，Token不会被刷新
 * - 结果：用户一直在浏览，但30分钟后Token过期了，一点"收藏"就掉线了，体验很差
 *
 * 两层拦截器的设计：
 * - 第一层（RefreshTokenInterceptor，order=0）：
 *   - 拦截所有请求（/**）
 *   - 有Token就解析用户、刷新Token有效期
 *   - 没有Token也放行，不做登录校验
 * - 第二层（LoginInterceptor，order=1）：
 *   - 只拦截需要登录的路径
 *   - 检查ThreadLocal里有没有用户，没有就拦截
 *
 * 这样设计的好处：
 * 1. 职责分离：第一层刷新Token，第二层校验登录
 * 2. 性能优化：不需要登录的路径不做多余的校验
 * 3. 用户体验：用户一直在操作，Token就一直有效
 * 4. 复用数据：第一层已经把用户放到ThreadLocal了，第二层直接用
 *
 * 【八股：Spring MVC拦截器的执行顺序】
 * - order值越小，优先级越高，越先执行
 * - preHandle：按order从小到大执行
 * - postHandle / afterCompletion：按order从大到小执行（倒序）
 * - 可以理解为洋葱模型：先进后出
 *
 * 【八股：HandlerInterceptor的三个方法】
 * - preHandle：请求处理前执行，返回true放行，返回false拦截
 * - postHandle：请求处理后、视图渲染前执行
 * - afterCompletion：整个请求完成后执行（不管成功失败），适合做资源清理
 */
public class RefreshTokenInterceptor implements HandlerInterceptor {

    private  StringRedisTemplate stringRedisTemplate;

    public RefreshTokenInterceptor(StringRedisTemplate stringRedisTemplate) {
        this.stringRedisTemplate=stringRedisTemplate;
    }


    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        //1.获取请求头中的token
        String token = request.getHeader("authorization");
        //2.基于token获取redis中的用户
        if (StrUtil.isBlank(token)) {
            // 【八股：为什么没有Token也放行？】
            // 因为这是第一层拦截器，只负责刷新Token，不负责校验登录
            // 有些接口不需要登录（比如查看商铺），没有Token也应该能访问
            // 登录校验交给第二层LoginInterceptor去做
            return true;
        }
        String userKey = RedisConstants.LOGIN_USER_KEY + token;
        Map<Object, Object> map = stringRedisTemplate.opsForHash().entries(userKey);
        //3.判断用户是否存在
        if(map.isEmpty()) {
            return true;
        }
        //5.将查询到Hash数据转换为userDTO对象
        UserDTO userDTO = BeanUtil.fillBeanWithMap(map, new UserDTO(), false);
        //6.存在，保存用户信息到ThreadLocal
        // 【八股：为什么要存到ThreadLocal？】
        // 1. 线程安全：每个线程有自己的ThreadLocal，多线程下互不干扰
        // 2. 传递数据：同一个请求的后续流程（service、dao）都可以直接获取用户
        // 3. 解耦：不需要在方法参数中到处传User对象
        // 4. 性能：不用每次都从Redis查，一次请求只查一次
        UserHolder.saveUser(userDTO);
        //7.刷新有效期
        // 【八股：为什么要刷新Token有效期？】
        // 类似Session的过期机制：用户活跃期间，Token应该一直有效
        // 用户每次操作都刷新一下，30分钟不操作才过期
        // 这样既安全（长期不用自动过期），又不影响用户体验
        stringRedisTemplate.expire(userKey,30, TimeUnit.MINUTES);
        //放行
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) throws Exception {
        // 【八股：这里应该调用UserHolder.removeUser()！】
        // 本代码有个小问题：没有在afterCompletion中清理ThreadLocal
        // 因为Tomcat用的是线程池，线程会被复用
        // 如果不清理，下一个请求可能拿到上一个请求的用户信息，造成数据错乱
        // 这是面试中的常见考点：ThreadLocal内存泄漏 + 线程复用导致的数据污染
        // HandlerInterceptor.super.afterCompletion(request, response, handler, ex);
    }
}
