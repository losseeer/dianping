package com.hmdp.utils;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;

class ConfirmedRabbitPublisherTest {

    private RabbitTemplate rabbitTemplate;
    private ConfirmedRabbitPublisher publisher;

    @BeforeEach
    void setUp() {
        rabbitTemplate = mock(RabbitTemplate.class);
        publisher = new ConfirmedRabbitPublisher();
        ReflectionTestUtils.setField(publisher, "rabbitTemplate", rabbitTemplate);
    }

    @Test
    void acceptsConfirmedRoutableMessage() {
        completePublish(true, false);
        assertDoesNotThrow(() -> publisher.send("exchange", "key", "payload", "id-1"));
    }

    @Test
    void rejectsBrokerNack() {
        completePublish(false, false);
        assertThrows(IllegalStateException.class,
                () -> publisher.send("exchange", "key", "payload", "id-2"));
    }

    @Test
    void rejectsUnroutableMessage() {
        completePublish(true, true);
        assertThrows(IllegalStateException.class,
                () -> publisher.send("exchange", "key", "payload", "id-3"));
    }

    private void completePublish(boolean ack, boolean returned) {
        ArgumentCaptor<CorrelationData> captor = ArgumentCaptor.forClass(CorrelationData.class);
        doAnswer(invocation -> {
            CorrelationData correlationData = invocation.getArgument(3);
            if (returned) {
                correlationData.setReturnedMessage(
                        new Message(new byte[0], new MessageProperties()));
            }
            correlationData.getFuture().set(new CorrelationData.Confirm(ack, ack ? null : "nack"));
            return null;
        }).when(rabbitTemplate).convertAndSend(
                eq("exchange"), eq("key"), eq("payload"), captor.capture());
    }
}
