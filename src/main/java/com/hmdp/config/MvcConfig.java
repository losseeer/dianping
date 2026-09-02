package com.hmdp.config;

import com.hmdp.interceptor.LoginInterceptor;
import com.hmdp.interceptor.RefreshTokenInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import javax.annotation.Resource;

@Configuration
public class MvcConfig implements WebMvcConfigurer {
    @Resource
    private StringRedisTemplate stringRedisTemplate;
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        //登录拦截器
        // 【已知缺陷，面试可主动讲】白名单按前缀放行过宽：
        // /voucher/**、/shop/**、/upload/** 把 POST/PUT 写操作也放行了
        // （发券、改店铺、上传/删除文件无需登录即可调用），生产应只放行 GET 查询类路径，
        // 写操作必须登录 + 角色校验（管理员），上传接口还要加后缀白名单和路径穿越校验
        registry.addInterceptor(new LoginInterceptor())
                .excludePathPatterns(
                        "/user/login",
                        "/upload/**",
                        "/voucher/**",
                        "/user/code",
                        "/shop/**",
                        "/shop-type/**",
                        "/blog/hot",
                        // 【八股：支付回调接口需要排除登录拦截器】
                        // 第三方支付平台调用回调时不会携带用户登录Token
                        // 如果不排除，回调会被拦截器返回401，导致支付状态无法更新
                        "/pay/notify",
                        "/pay/refund/callback",
                        // 推荐接口：附近热门和全站热门不需要登录
                        "/recommend/hot",
                        "/recommend/nearby"
                ).order(1);
        //token刷新的拦截器
        registry.addInterceptor(new RefreshTokenInterceptor(stringRedisTemplate))
                .addPathPatterns("/**").order(0);
    }
}
