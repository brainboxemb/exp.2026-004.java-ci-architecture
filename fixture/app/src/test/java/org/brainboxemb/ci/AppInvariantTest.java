package org.brainboxemb.ci;

import org.junit.Test;
import static org.junit.Assert.assertTrue;

public class AppInvariantTest {
    @Test
    public void containsBothFeatureValues() {
        String message = App.message();
        assertTrue(message.startsWith("core-a"));
        assertTrue(message.endsWith("core-b"));
    }
}
