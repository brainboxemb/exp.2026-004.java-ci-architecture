package org.brainboxemb.ci;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

public class FeatureATest {
    @Test
    public void usesCore() {
        assertEquals("core-a", FeatureA.value());
    }
}
