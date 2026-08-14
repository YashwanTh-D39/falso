import logging
from typing import Any, List, Dict, Optional

logger = logging.getLogger(__name__)

class UIAutomation:
    def __init__(self):
        self._available = False
        self.uia = None
        self.root = None
        self.UIAutomationClient = None
        self._initialize_uia()

    def _initialize_uia(self):
        try:
            import comtypes
            import comtypes.client
            comtypes.CoInitialize()
            
            try:
                comtypes.client.GetModule('UIAutomationCore.dll')
            except Exception as e:
                logger.warning(f"[UI_AUTOMATION] Failed to load UIAutomationCore module: {e}")

            from comtypes.gen import UIAutomationClient
            self.UIAutomationClient = UIAutomationClient

            CLSID_CUIAutomation = '{FF48DBA4-60EF-4201-AA87-54103EEF594E}'
            self.uia = comtypes.CoCreateInstance(
                comtypes.GUID(CLSID_CUIAutomation),
                interface=UIAutomationClient.IUIAutomation,
                clsctx=comtypes.CLSCTX_INPROC_SERVER
            )
            self.root = self.uia.GetRootElement()
            self._available = True
            logger.info("[UI_AUTOMATION] Initialized UIA COM successfully.")
        except Exception as e:
            logger.warning(f"[UI_AUTOMATION] Failed to initialize UIA COM: {e}")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def _get_start_element(self, window_title: Optional[str] = None):
        if not self.is_available():
            return None
        if window_title:
            try:
                condition = self.uia.CreatePropertyCondition(self.UIAutomationClient.UIA_NamePropertyId, window_title)
                return self.root.FindFirst(self.UIAutomationClient.TreeScope_Children, condition)
            except Exception:
                return None
        return self.root

    def discover_elements(self, window_title: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        
        start_element = self._get_start_element(window_title)
        if not start_element:
            return []

        elements = []
        queue = [(start_element, 0)]
        max_depth = 3
        max_results = 50
        
        try:
            true_condition = self.uia.CreateTrueCondition()
        except Exception:
            return []
        
        while queue and len(elements) < max_results:
            elem, depth = queue.pop(0)
            
            try:
                name = elem.CurrentName
                ctrl_type = elem.CurrentControlType
                auto_id = elem.CurrentAutomationId
                enabled = elem.CurrentIsEnabled
                rect = elem.CurrentBoundingRectangle
                
                elements.append({
                    'name': name,
                    'role': str(ctrl_type),
                    'control_type': str(ctrl_type),
                    'automation_id': auto_id,
                    'enabled': enabled,
                    'visible': not elem.CurrentIsOffscreen,
                    'bounding_rect': {'left': rect.left, 'top': rect.top, 'right': rect.right, 'bottom': rect.bottom} if rect else None
                })
            except Exception:
                pass
            
            if depth < max_depth:
                try:
                    children = elem.FindAll(self.UIAutomationClient.TreeScope_Children, true_condition)
                    if children:
                        for i in range(children.Length):
                            queue.append((children.GetElement(i), depth + 1))
                except Exception:
                    pass

        return elements[:max_results]

    def _build_condition(self, name, role, automation_id, control_type):
        conditions = []
        try:
            if name is not None:
                conditions.append(self.uia.CreatePropertyCondition(self.UIAutomationClient.UIA_NamePropertyId, name))
            if automation_id is not None:
                conditions.append(self.uia.CreatePropertyCondition(self.UIAutomationClient.UIA_AutomationIdPropertyId, automation_id))
            
            if not conditions:
                return self.uia.CreateTrueCondition()
            if len(conditions) == 1:
                return conditions[0]
            
            # Simple conversion to array if multiple
            return self.uia.CreateAndConditionFromArray(conditions)
        except Exception as e:
            logger.warning(f"[UI_AUTOMATION] Failed to build condition: {e}")
            return None

    def _find_raw_element(self, name, role, automation_id, control_type, window_title):
        if not self.is_available():
            return None
        start_element = self._get_start_element(window_title)
        if not start_element:
            return None

        condition = self._build_condition(name, role, automation_id, control_type)
        if not condition:
            return None
        
        try:
            return start_element.FindFirst(self.UIAutomationClient.TreeScope_Descendants, condition)
        except Exception:
            return None

    def find_element(self, name: Optional[str] = None, role: Optional[str] = None, automation_id: Optional[str] = None, control_type: Optional[str] = None, window_title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        elem = self._find_raw_element(name, role, automation_id, control_type, window_title)
        if not elem:
            return None
        
        try:
            rect = elem.CurrentBoundingRectangle
            return {
                'name': elem.CurrentName,
                'role': str(elem.CurrentControlType),
                'control_type': str(elem.CurrentControlType),
                'automation_id': elem.CurrentAutomationId,
                'enabled': elem.CurrentIsEnabled,
                'visible': not elem.CurrentIsOffscreen,
                'bounding_rect': {'left': rect.left, 'top': rect.top, 'right': rect.right, 'bottom': rect.bottom} if rect else None
            }
        except Exception:
            return None

    def get_element_value(self, name: Optional[str] = None, automation_id: Optional[str] = None, window_title: Optional[str] = None) -> Optional[str]:
        elem = self._find_raw_element(name, None, automation_id, None, window_title)
        if not elem:
            return None
        try:
            val_pattern = elem.GetCurrentPattern(self.UIAutomationClient.UIA_ValuePatternId)
            if val_pattern:
                pattern = val_pattern.QueryInterface(self.UIAutomationClient.IUIAutomationValuePattern)
                return pattern.CurrentValue

            text_pattern = elem.GetCurrentPattern(self.UIAutomationClient.UIA_TextPatternId)
            if text_pattern:
                pattern = text_pattern.QueryInterface(self.UIAutomationClient.IUIAutomationTextPattern)
                return pattern.DocumentRange.GetText(-1)
        except Exception as e:
            logger.warning(f"[UI_AUTOMATION] get_element_value failed: {e}")
        return None

    def get_element_text(self, name: Optional[str] = None, automation_id: Optional[str] = None, window_title: Optional[str] = None) -> Optional[str]:
        elem = self._find_raw_element(name, None, automation_id, None, window_title)
        if not elem:
            return None
        try:
            if elem.CurrentName:
                return elem.CurrentName
            return self.get_element_value(name, automation_id, window_title)
        except Exception:
            return None

    def get_element_state(self, name: Optional[str] = None, automation_id: Optional[str] = None, window_title: Optional[str] = None) -> Dict[str, Any]:
        elem = self._find_raw_element(name, None, automation_id, None, window_title)
        if not elem:
            return {}
        try:
            return {
                'enabled': elem.CurrentIsEnabled,
                'focused': elem.CurrentHasKeyboardFocus,
                'offscreen': elem.CurrentIsOffscreen
            }
        except Exception:
            return {}

    def click_element(self, name: str, role: str = 'button', window_title: Optional[str] = None) -> bool:
        elem = self._find_raw_element(name, role, None, None, window_title)
        if not elem:
            return False
        try:
            invoke_pattern = elem.GetCurrentPattern(self.UIAutomationClient.UIA_InvokePatternId)
            if invoke_pattern:
                pattern = invoke_pattern.QueryInterface(self.UIAutomationClient.IUIAutomationInvokePattern)
                pattern.Invoke()
                return True
                
            selection_pattern = elem.GetCurrentPattern(self.UIAutomationClient.UIA_SelectionItemPatternId)
            if selection_pattern:
                pattern = selection_pattern.QueryInterface(self.UIAutomationClient.IUIAutomationSelectionItemPattern)
                pattern.Select()
                return True
            return False
        except Exception as e:
            logger.warning(f"[UI_AUTOMATION] click_element failed: {e}")
            return False

    def select_element(self, name: str, window_title: Optional[str] = None) -> bool:
        elem = self._find_raw_element(name, None, None, None, window_title)
        if not elem:
            return False
        try:
            selection_pattern = elem.GetCurrentPattern(self.UIAutomationClient.UIA_SelectionItemPatternId)
            if selection_pattern:
                pattern = selection_pattern.QueryInterface(self.UIAutomationClient.IUIAutomationSelectionItemPattern)
                pattern.Select()
                return True
            return False
        except Exception:
            return False

    def set_text(self, name: Optional[str] = None, automation_id: Optional[str] = None, text: str = '', window_title: Optional[str] = None) -> bool:
        elem = self._find_raw_element(name, None, automation_id, None, window_title)
        if not elem:
            return False
        try:
            val_pattern = elem.GetCurrentPattern(self.UIAutomationClient.UIA_ValuePatternId)
            if val_pattern:
                pattern = val_pattern.QueryInterface(self.UIAutomationClient.IUIAutomationValuePattern)
                pattern.SetValue(text)
                return True
            return False
        except Exception as e:
            logger.warning(f"[UI_AUTOMATION] set_text failed: {e}")
            return False

ui_automation = UIAutomation()
