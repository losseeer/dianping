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
 * 登录拦截器（第二层拦截器，order=1）
 *
 * 【八股：拦截器 vs 过滤器（Filter）的区别】
 *
 * 1. 所属层级不同：
 *    - Filter是Servlet规范的，在DispatcherServlet之前执行
 *    - Interceptor是Spring MVC的，在DispatcherServlet之后、Controller之前执行
 *
 * 2. 依赖不同：
 *    - Filter不依赖Spring容器，是Servlet级别的
 *    - Interceptor依赖Spring容器，可以注入Spring Bean
 *
 * 3. 执行顺序：
 *    - 请求进来：Filter → Interceptor → Controller
 *    - 响应回去：Controller → Interceptor → Filter
 *
 * 4. 拦截范围：
 *    - Filter几乎能拦截所有进入容器的请求
 *    - Interceptor只能拦截Controller请求（静态资源不拦截）
 *
 * 5. 应用场景：
 *    - Filter：编码转换、跨域处理、XSS防护等通用请求处理
 *    - Interceptor：登录校验、权限控制、日志记录等业务相关的拦截
 *
 * 本项目用Interceptor而不是Filter的原因：
 * - 需要注入StringRedisTemplate，Interceptor可以直接注入
 * - 只需要拦截Controller请求，不需要管静态资源
 * - 和Spring MVC集成更好
 */
public class LoginInterceptor implements HandlerInterceptor {
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
       //1.判断是否需要拦截（ThreadLocal）中是否有用户
       // 【八股：为什么从ThreadLocal取，而不是再查一次Redis？】
       // 1. 性能：ThreadLocal是内存操作，比Redis快得多
       // 2. 复用：第一层拦截器已经查过Redis了，没必要再查一次
       // 3. 解耦：业务代码不需要关心用户从哪来的，直接从UserHolder取就行
        if(UserHolder.getUser()==null){
            //没有需要拦截，设置状态码
            response.setStatus(401);
            //拦截
            return false;
        }
        //由用户放行
        return true;
    }
}
