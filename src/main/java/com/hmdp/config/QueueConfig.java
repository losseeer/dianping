package com.hmdp.config;
import org.springframework.amqp.core.*;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.HashMap;
@Configuration
public class QueueConfig {

    //普通交换机名称
    public static final String X_EXCHANGE="X";
    //死信交换机名称
    public static final String Y_DEAD_LETTER_EXCHANGE="Y";
    //普通队列名称
    public static final String QUEUE_A="QA";
    //死信队列名称
    public static final String DEAD_LETTER_QUEUE_D="QD";

    // ==================== 交易闭环模块队列配置 ====================

    /**
     * 订单延迟队列相关配置 —— 【八股：RabbitMQ延迟队列实现方案】
     *
     * 【八股：RabbitMQ如何实现延迟队列？】
     * RabbitMQ本身没有直接支持延迟队列，但有三种常用方案：
     * 1. 死信队列(DLX) + TTL：消息设置TTL过期后进入死信队列，消费者从死信队列消费
     *    - 优点：不需要额外插件
     *    - 缺点：TTL有队头阻塞问题（后面的消息即使先过期也要等前面的过期）
     * 2. rabbitmq_delayed_message_exchange插件：消息直接延迟投递
     *    - 优点：没有队头阻塞问题，支持任意延迟时间
     *    - 缺点：需要安装插件
     * 3. Spring的delayed-message-exchange：基于插件封装
     *
     * 本项目使用方案1（死信队列+TTL），因为不需要额外安装插件
     *
     * 订单延迟流程：
     *   消息 → ORDER_DELAY_EXCHANGE → ORDER_DELAY_QUEUE(TTL 30min)
     *   → 30分钟后消息过期 → ORDER_DEAD_EXCHANGE → ORDER_CANCEL_QUEUE
     *   → OrderDelayListener消费，执行超时取消
     */

    // 订单延迟 - 普通交换机
    public static final String ORDER_DELAY_EXCHANGE = "order.delay.exchange";
    // 订单延迟 - 死信交换机
    public static final String ORDER_DEAD_EXCHANGE = "order.dead.exchange";
    // 订单延迟 - 普通队列（TTL 30分钟）
    public static final String ORDER_DELAY_QUEUE = "order.delay.queue";
    // 订单取消 - 死信队列（消费者从这里获取超时订单）
    public static final String ORDER_CANCEL_QUEUE = "order.cancel.queue";
    // 订单延迟路由键
    public static final String ORDER_DELAY_ROUTING_KEY = "order.delay";
    // 订单取消路由键（死信路由键）
    public static final String ORDER_CANCEL_ROUTING_KEY = "order.dead";
    /**
     * 订单超时时间 —— 30分钟 = 1800000毫秒
     * 【八股：为什么是30分钟？】
     * 这是电商行业的通用标准，淘宝/京东/美团都是15-30分钟自动取消未支付订单
     * 时间太短：用户可能还在犹豫，或者支付过程中遇到问题
     * 时间太长：库存被占用，影响其他用户购买
     */
    public static final int ORDER_DELAY_TTL = 1800000;

    /**
     * 支付通知队列 —— 支付成功后异步通知用户
     * 【八股：为什么支付通知要异步？】
     * 1. 支付回调要快速返回（第三方支付平台有超时限制，通常5秒）
     * 2. 发短信/推送通知耗时较长，不应阻塞支付回调
     * 3. 即使通知失败也不影响支付本身（最终一致性）
     */
    public static final String PAY_NOTIFY_EXCHANGE = "pay.notify.exchange";
    public static final String PAY_NOTIFY_QUEUE = "pay.notify.queue";
    public static final String PAY_NOTIFY_ROUTING_KEY = "pay.notify";

    /**
     * 退款队列 —— 异步处理退款
     * 【八股：为什么退款要异步？】
     * 1. 退款涉及第三方支付平台的API调用，耗时不确定
     * 2. 退款需要恢复库存、删除一人一单记录等操作，比较复杂
     * 3. 异步处理可以重试失败的操作
     */
    public static final String REFUND_EXCHANGE = "refund.exchange";
    public static final String REFUND_QUEUE = "refund.queue";
    public static final String REFUND_ROUTING_KEY = "refund";


    /**
     * 声明x交换机
     * @return
     */
    @Bean("xExchange")//别名和方法名取一样
    public DirectExchange xExchange(){
        return new DirectExchange(X_EXCHANGE);
    }

    /**
     * 声明y交换机
     * @return
     */
    @Bean("yExchange")//别名和方法名取一样
    public DirectExchange yExchange(){
        return new DirectExchange(Y_DEAD_LETTER_EXCHANGE);
    }

    /**
     * 声明队列A
     * @return
     */
    @Bean("queueA")
    public Queue queueA(){
        final HashMap<String, Object> arguments
                = new HashMap<>();
        //设置死信交换机
        arguments.put("x-dead-letter-exchange",Y_DEAD_LETTER_EXCHANGE);
        //设置死信RoutingKey
        arguments.put("x-dead-letter-routing-key","YD");
        //设置TTL设置10秒过期
        arguments.put("x-message-ttl",10000);

        return QueueBuilder.durable(QUEUE_A)
                .withArguments(arguments)
                .build();
    }

    /**
     * 声明死信队列D
     * @return
     */
    @Bean("queueD")
    public Queue queueD(){
        return QueueBuilder.durable(DEAD_LETTER_QUEUE_D)
                .build();
    }

    /**
     * A队列绑定X交换机
     * @param queueA
     * @return
     */
    @Bean
    public Binding queueABindingX(@Qualifier("queueA")Queue queueA,
                                  @Qualifier("xExchange") DirectExchange xExchange){
        return BindingBuilder.bind(queueA).to(xExchange).with("XA");
    }

    /**
     * d队列绑定y交换机
     * @param queueD
     * @return
     */
    @Bean
    public  Binding queueDBindingY(@Qualifier("queueD")Queue queueD,
                                   @Qualifier("yExchange") DirectExchange yExchange
    ){
        return BindingBuilder.bind(queueD).to(yExchange).with("YD");
    }


    // ==================== 订单延迟队列配置 ====================

    /**
     * 声明订单延迟普通交换机 ORDER_DELAY_EXCHANGE
     * 【八股：DirectExchange vs TopicExchange vs FanoutExchange】
     * - DirectExchange：精确匹配routingKey，一对一
     * - TopicExchange：模式匹配routingKey（支持*和#通配符），一对多
     * - FanoutExchange：广播，不看routingKey，一对所有
     * 订单延迟只需要精确路由，用DirectExchange即可
     */
    @Bean("orderDelayExchange")
    public DirectExchange orderDelayExchange(){
        return new DirectExchange(ORDER_DELAY_EXCHANGE);
    }

    /**
     * 声明订单死信交换机 ORDER_DEAD_EXCHANGE
     * 死信交换机接收过期消息，转发到ORDER_CANCEL_QUEUE
     */
    @Bean("orderDeadExchange")
    public DirectExchange orderDeadExchange(){
        return new DirectExchange(ORDER_DEAD_EXCHANGE);
    }

    /**
     * 声明订单延迟队列 ORDER_DELAY_QUEUE
     * 【八股：队列参数详解】
     * - x-dead-letter-exchange：消息过期后转发到哪个交换机
     * - x-dead-letter-routing-key：过期消息的路由键（会替换原始routingKey）
     * - x-message-ttl：队列中消息的默认TTL（毫秒），不设置则永不过期
     *
     * 注意：这里同时设置了队列级TTL和消息级TTL（在发送时设置）
     * 两者取较小值生效。如果队列级TTL=30min，消息级TTL也=30min，则都是30min过期
     */
    @Bean("orderDelayQueue")
    public Queue orderDelayQueue(){
        HashMap<String, Object> arguments = new HashMap<>();
        // 绑定死信交换机
        arguments.put("x-dead-letter-exchange", ORDER_DEAD_EXCHANGE);
        // 设置死信路由键
        arguments.put("x-dead-letter-routing-key", ORDER_CANCEL_ROUTING_KEY);
        // 设置队列级TTL为30分钟
        arguments.put("x-message-ttl", ORDER_DELAY_TTL);

        return QueueBuilder.durable(ORDER_DELAY_QUEUE)
                .withArguments(arguments)
                .build();
    }

    /**
     * 声明订单取消死信队列 ORDER_CANCEL_QUEUE
     * 消费者从此队列获取超时未支付的订单，执行自动取消
     */
    @Bean("orderCancelQueue")
    public Queue orderCancelQueue(){
        return QueueBuilder.durable(ORDER_CANCEL_QUEUE)
                .build();
    }

    /**
     * 订单延迟队列绑定到普通交换机
     */
    @Bean
    public Binding orderDelayQueueBinding(@Qualifier("orderDelayQueue") Queue orderDelayQueue,
                                           @Qualifier("orderDelayExchange") DirectExchange orderDelayExchange){
        return BindingBuilder.bind(orderDelayQueue).to(orderDelayExchange).with(ORDER_DELAY_ROUTING_KEY);
    }

    /**
     * 订单取消队列绑定到死信交换机
     */
    @Bean
    public Binding orderCancelQueueBinding(@Qualifier("orderCancelQueue") Queue orderCancelQueue,
                                            @Qualifier("orderDeadExchange") DirectExchange orderDeadExchange){
        return BindingBuilder.bind(orderCancelQueue).to(orderDeadExchange).with(ORDER_CANCEL_ROUTING_KEY);
    }


    // ==================== 支付通知队列配置 ====================

    /**
     * 声明支付通知交换机
     */
    @Bean("payNotifyExchange")
    public DirectExchange payNotifyExchange(){
        return new DirectExchange(PAY_NOTIFY_EXCHANGE);
    }

    /**
     * 声明支付通知队列
     */
    @Bean("payNotifyQueue")
    public Queue payNotifyQueue(){
        return QueueBuilder.durable(PAY_NOTIFY_QUEUE).build();
    }

    /**
     * 支付通知队列绑定到交换机
     */
    @Bean
    public Binding payNotifyQueueBinding(@Qualifier("payNotifyQueue") Queue payNotifyQueue,
                                          @Qualifier("payNotifyExchange") DirectExchange payNotifyExchange){
        return BindingBuilder.bind(payNotifyQueue).to(payNotifyExchange).with(PAY_NOTIFY_ROUTING_KEY);
    }


    // ==================== 退款队列配置 ====================

    /**
     * 声明退款交换机
     */
    @Bean("refundExchange")
    public DirectExchange refundExchange(){
        return new DirectExchange(REFUND_EXCHANGE);
    }

    /**
     * 声明退款队列
     */
    @Bean("refundQueue")
    public Queue refundQueue(){
        return QueueBuilder.durable(REFUND_QUEUE).build();
    }

    /**
     * 退款队列绑定到交换机
     */
    @Bean
    public Binding refundQueueBinding(@Qualifier("refundQueue") Queue refundQueue,
                                      @Qualifier("refundExchange") DirectExchange refundExchange){
        return BindingBuilder.bind(refundQueue).to(refundExchange).with(REFUND_ROUTING_KEY);
    }


}
