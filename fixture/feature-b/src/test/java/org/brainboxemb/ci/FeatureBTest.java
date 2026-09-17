package org.brainboxemb.ci;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

public class FeatureBTest {
    @Test
    public void usesCore() {
        assertEquals("core-b", FeatureB.value());
    }
}
