package com.hmdp.utils;

import com.hmdp.dto.UserDTO;

/**
 * 用户上下文持有者 —— 【八股：ThreadLocal 原理与内存泄漏】
 *
 * 【八股：ThreadLocal是干什么的？】
 * ThreadLocal提供了线程局部变量，每个线程都有自己独立的一份变量副本
 * 线程之间互不干扰，解决了多线程环境下的数据隔离问题
 *
 * 【八股：ThreadLocal的原理】
 * - 每个Thread对象内部都有一个ThreadLocalMap成员变量
 * - ThreadLocalMap的key是ThreadLocal对象本身（弱引用），value是线程的变量值
 * - 当调用threadLocal.set(value)时，其实是往当前线程的ThreadLocalMap里存数据
 * - 当调用threadLocal.get()时，从当前线程的ThreadLocalMap里取数据
 *
 * 【八股：ThreadLocal为什么会内存泄漏？】
 * 关键：ThreadLocalMap的key是弱引用(WeakReference)，value是强引用
 *
 * 内存泄漏场景：
 * 1. ThreadLocal对象被回收了（没有强引用指向它）
 * 2. 但线程还活着（比如线程池中的线程）
 * 3. ThreadLocalMap里的Entry的key（弱引用）被GC回收了，变成null
 * 4. 但value是强引用，不会被回收
 * 5. 这个value就永远无法被访问到，也无法被回收 → 内存泄漏
 *
 * 【八股：如何避免ThreadLocal内存泄漏？】
 * 1. 每次使用完ThreadLocal，手动调用remove()方法（本项目就应该在拦截器afterCompletion里调用）
 * 2. 使用完及时清理是最佳实践，不要依赖弱引用机制
 * 3. 如果线程是线程池中的，更要注意remove，因为线程会被复用
 *
 * 【八股：ThreadLocalMap的key为什么要设计成弱引用？】
 * 如果key是强引用，即使ThreadLocal对象没有外部引用了，也不会被回收
 * 因为Thread -> ThreadLocalMap -> Entry(key) -> ThreadLocal 这条强引用链还在
 * 设计成弱引用，就是为了让ThreadLocal对象在没有外部强引用时能被正常回收
 * 但这又引入了value泄漏的问题，所以需要手动remove
 *
 * 【八股：ThreadLocal的应用场景】
 * - 保存用户登录信息（本项目就是这个用法）
 * - 数据库连接管理（每个线程一个连接）
 * - 事务管理（保证同一个线程用同一个连接）
 * - 日期格式化（SimpleDateFormat线程不安全，用ThreadLocal每个线程一个）
 * - 全链路追踪traceId传递
 */
public class UserHolder {
    private static final ThreadLocal<UserDTO> tl = new ThreadLocal<>();

    public static void saveUser(UserDTO user){
        tl.set(user);
    }

    public static UserDTO getUser(){
        return tl.get();
    }

    public static void removeUser(){
        tl.remove();
    }
}
