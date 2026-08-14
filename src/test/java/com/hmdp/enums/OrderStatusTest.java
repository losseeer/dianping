package com.hmdp.enums;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class OrderStatusTest {

    @Test
    void onlyAllowsSupportedOrderTransitions() {
        assertTrue(OrderStatus.UNPAID.canTransitionTo(OrderStatus.PAID));
        assertTrue(OrderStatus.UNPAID.canTransitionTo(OrderStatus.CANCELLED));
        assertFalse(OrderStatus.CANCELLED.canTransitionTo(OrderStatus.PAID));
        assertTrue(OrderStatus.PAID.canTransitionTo(OrderStatus.REFUNDING));
        assertTrue(OrderStatus.REFUNDING.canTransitionTo(OrderStatus.REFUNDED));
        assertFalse(OrderStatus.REFUNDED.canTransitionTo(OrderStatus.REFUNDING));
    }
}
