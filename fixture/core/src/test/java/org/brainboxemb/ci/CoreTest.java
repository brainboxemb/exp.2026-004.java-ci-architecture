package org.brainboxemb.ci;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

public class CoreTest {
    @Test
    public void returnsStableValue() {
        assertEquals("core", Core.value());
    }
}
