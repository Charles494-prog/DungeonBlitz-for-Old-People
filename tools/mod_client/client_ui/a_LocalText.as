package
{
   import flash.display.DisplayObject;
   import flash.display.MovieClip;
   import flash.display.Sprite;
   import flash.events.IOErrorEvent;
   import flash.events.MouseEvent;
   import flash.events.SecurityErrorEvent;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import flash.filters.DropShadowFilter;
   import flash.filters.GlowFilter;
   import flash.text.TextField;
   import flash.text.TextFormat;

   // a_LocalText is the client's own class (text that localizes itself); it decompiles
   // cleanly, so tools/patch_client_timers.py recompiles it with the Mount Merchant
   // window added as static functions. MathUtil.method_259 (every server status
   // message passes through it) is patched to call mmHook first.
   public class a_LocalText extends MovieClip
   {

      public static var funcRef:Function;

      // "\u0001MM|0|<idols>|<sigils>|<gold>|<id>:<G|I|S>:<price>:<owned>,..." (every mount)
      private static const MM_MARK:String = "\u0001MM|";
      private static const WS_MARK:String = "\u0001WS|";
      private static const KY_MARK:String = "\u0001KY|";
      private static const PG_MARK:String = "\u0001PG|";

      // Paragon level (levels after 50): the server says it ("\u0001PG|<level>") at login and
      // on a level-up; every gear stat grows PARAGON_STAT_BONUS per level (gearStat)
      private static var paragon:int = 0;
      private static const PARAGON_STAT_BONUS:Number = __PARAGON_STAT_BONUS__;

      // Riding speed: every mount gives the same "Mounted" buff (SpeedChange 0.4, i.e. +40%).
      // CombatState.method_322 copies it into var_2405 through mountSpeed: Rare and Legendary
      // mounts ride faster.
      private static const RARE_MOUNT_SPEED:Number = __RARE_MOUNT_SPEED__;
      private static const LEGENDARY_MOUNT_SPEED:Number = __LEGENDARY_MOUNT_SPEED__;

      public static function mountSpeed(param1:CombatState, param2:Number) : Number
      {
         var _loc3_:Entity = !!param1 ? param1.var_3 : null;
         var _loc4_:String = !!(_loc3_ && _loc3_.mEquipMount) ? _loc3_.mEquipMount.var_255 : "M";
         if(_loc4_ == "L")
         {
            return Math.max(param2,LEGENDARY_MOUNT_SPEED);
         }
         if(_loc4_ == "R")
         {
            return Math.max(param2,RARE_MOUNT_SPEED);
         }
         return param2;
      }
      private static const W:Number = 960;
      private static const H:Number = 540;
      private static const GOLD:uint = 0xC9A227;
      private static const CREAM:uint = 0xF5E6C8;
      private static const RED:uint = 0xFF5A4A;
      private static const GREEN:uint = 0x7CE05A;
      private static const PER_PAGE:int = 12; // 6 x 2 slots

      private static var mmWin:Sprite;
      private static var mmItems:Array;
      private static var mmSel:int = 0;
      private static var mmPage:int = 0;
      private static var mmWallet:Object;
      private static var mmBusy:Boolean = false;
      private static var mmSlots:Array;
      private static var mmPreview:Sprite;
      private static var mmOwned:TextField;
      private static var mmPageText:TextField;
      private static var mmRarity:TextField;
      private static var mmName:TextField;
      private static var mmDesc:TextField;
      private static var mmPrice:TextField;
      private static var mmYours:TextField;
      private static var mmBuy:Sprite;

      public function a_LocalText()
      {
         super();
         funcRef(this);
      }

      // Game.method_1916 (talking to an NPC in the keep, which the client handles
      // itself) is patched to call this first: the Stablemaster asks the server for
      // the Mount Merchant's stock, which comes back as the MM_MARK message.
      public static function mmTalk(param1:String) : void
      {
         var _loc2_:Game = SuperAnimData.aaMain.var_523[0];
         if(param1 == "Special_Stablemaster" && _loc2_)
         {
            _loc2_.linkUpdater.WriteChatMessage(_loc2_.clientEntID,"!mmopen");
         }
      }

      // "\u0001WS|1" / "\u0001WS|0": the 16:9 (1366 wide) or the original 3:2 (1152) view.
      // Main.method_561 lays the game out again; it rebuilds its buffers only when the
      // scale changes, hence overallScale = 0 first.
      private static function mmWidescreen(param1:Boolean) : void
      {
         var _loc2_:Main = SuperAnimData.aaMain;
         Camera.SCREEN_WIDTH = param1 ? 1366 : 1152;
         _loc2_.overallScale = 0;
         _loc2_.method_561(_loc2_.stage.stageWidth,_loc2_.stage.stageHeight);
      }

      // class_63.method_1131 (the Mammoth Idol window's Buy button) is patched to call
      // this instead of navigateToURL(request, "_blank"): the purchase goes to the server
      // in the background rather than opening a browser tab.
      public static function mmLoadUrl(param1:URLRequest, param2:String = null) : void
      {
         var _loc3_:URLLoader = new URLLoader();
         _loc3_.addEventListener(IOErrorEvent.IO_ERROR,mmIgnore);
         _loc3_.addEventListener(SecurityErrorEvent.SECURITY_ERROR,mmIgnore);
         _loc3_.load(param1);
      }

      private static function mmIgnore(param1:Object) : void
      {
      }

      // Loot (a gear drop on the ground) is patched to glow in lootGlow(gearType, its
      // original colour): Legendary gold, Rare blue, Magic the original green.
      public static function lootGlow(param1:GearType, param2:uint) : uint
      {
         if(!param1)
         {
            return param2;
         }
         if(param1.var_8 == "L")
         {
            return 0xFFC21E;
         }
         if(param1.var_8 == "R")
         {
            return 0x2F9BFF;
         }
         return param2;
      }

      // The armory's gear list (ScreenArmory.method_2040) came in the game's gear-table
      // order, rarities mixed; it is patched to pass the list through here before it
      // returns: Legendary first, then Rare, then Magic, each in its old order.
      public static function sortGear(param1:Vector.<class_42>) : void
      {
         var _loc2_:Array = [];
         var _loc3_:Array = [];
         var _loc4_:Array = [];
         var _loc5_:class_42 = null;
         var _loc6_:String = null;
         var _loc7_:int = 0;
         for each(_loc5_ in param1)
         {
            _loc6_ = _loc5_ && _loc5_.gearType ? _loc5_.gearType.var_8 : "M";
            if(_loc6_ == "L")
            {
               _loc2_.push(_loc5_);
            }
            else if(_loc6_ == "R")
            {
               _loc3_.push(_loc5_);
            }
            else
            {
               _loc4_.push(_loc5_);
            }
         }
         for each(_loc5_ in _loc2_.concat(_loc3_,_loc4_))
         {
            param1[_loc7_++] = _loc5_;
         }
      }

      // GearType.method_121 (an item's Attack / Expertise / Armor at the wearer's level: used
      // by Entity.method_1457 for the real stats, by powers and by the tooltip) returns
      // through here. In the original, rarity only picked which stat table an item used,
      // so a Rare could beat a Legendary, and every stat grew with level (about 125 at level 1
      // to 1300+ at 50). Now each rarity has its own fixed range: Magic MAGIC_MIN..MAGIC_MAX,
      // Rare RARE_MIN..RARE_MAX, Legendary LEGENDARY_MIN..LEGENDARY_MAX. Where a stat falls in
      // its range follows where the game's own value sits among all the stat tables
      // (GearType.const_7), so higher-level and stronger items still land higher.
      // Legendaries get every stat. The numbers come from game_config
      // (tools/patch_client_timers.py writes them in when it compiles this).
      private static const MAGIC_MIN:Number = __MAGIC_STAT_MIN__;
      private static const MAGIC_MAX:Number = __MAGIC_STAT_MAX__;
      private static const RARE_MIN:Number = __RARE_STAT_MIN__;
      private static const RARE_MAX:Number = __RARE_STAT_MAX__;
      private static const LEGENDARY_MIN:Number = __LEGENDARY_STAT_MIN__;
      private static const LEGENDARY_MAX:Number = __LEGENDARY_STAT_MAX__;
      private static const LEGENDARY_EXTRA_STAT:Number = __LEGENDARY_EXTRA_STAT__;

      // the smallest and largest value in the game's stat tables (found once)
      private static var rawMin:Number = 0;
      private static var rawMax:Number = 0;

      // the game's value's place between rawMin and rawMax, mapped into min..max
      private static function inRange(param1:Number, param2:Number, param3:Number) : uint
      {
         var _loc5_:Array = null;
         var _loc6_:* = undefined;
         if(rawMax <= 0)
         {
            rawMin = Number.MAX_VALUE;
            for each(_loc5_ in GearType.const_7)
            {
               for each(_loc6_ in _loc5_)
               {
                  if(Number(_loc6_) > 0)
                  {
                     rawMin = Math.min(rawMin,Number(_loc6_));
                     rawMax = Math.max(rawMax,Number(_loc6_));
                  }
               }
            }
            if(rawMax <= rawMin)
            {
               rawMin = 0;
               rawMax = 1;
            }
         }
         var _loc4_:Number = (param1 - rawMin) / (rawMax - rawMin);
         _loc4_ = Math.max(0,Math.min(1,_loc4_));
         return uint(Math.round(param2 + (param3 - param2) * _loc4_));
      }

      public static function gearStat(param1:GearType, param2:String, param3:uint, param4:uint) : uint
      {
         return uint(rarityStat(param1,param2,param3,param4) * (1 + paragon * PARAGON_STAT_BONUS));
      }

      private static function rarityStat(param1:GearType, param2:String, param3:uint, param4:uint) : uint
      {
         var _loc5_:String = !!param1 ? param1.var_8 : "M";
         var _loc6_:Array = null;
         if(_loc5_ == "L")
         {
            if(param4 == 0)
            {
               // a stat the item's own table leaves out: a share of the standard one
               _loc6_ = GearType.const_7[param2 == "Attack" ? "Basic_Main_Mid" : (param2 == "Expertise" ? "Basic_Second_Mid" : (param2 == "Armor" ? "Basic_Armor_Mid" : ""))];
               if(_loc6_ && _loc6_.length)
               {
                  param4 = uint(uint(_loc6_[Math.min(param3,_loc6_.length - 1)]) * LEGENDARY_EXTRA_STAT);
               }
            }
            return param4 > 0 ? inRange(param4,LEGENDARY_MIN,LEGENDARY_MAX) : 0;
         }
         if(_loc5_ == "R")
         {
            return param4 > 0 ? inRange(param4,RARE_MIN,RARE_MAX) : 0;
         }
         return param4 > 0 ? inRange(param4,MAGIC_MIN,MAGIC_MAX) : 0;
      }

      // "\u0001KY|<n>": a monster dropped Dragon Keys. The client only adds keys itself when
      // they are bought (class_131.BuyLockboxKeys -> method_1303), so the server says so.
      private static function mmKeys(param1:uint) : String
      {
         var _loc2_:Game = SuperAnimData.aaMain.var_523[0];
         if(_loc2_ && _loc2_.mLockboxData)
         {
            _loc2_.mLockboxData.method_1303(param1);
         }
         return "You found " + param1 + (param1 == 1 ? " Dragon Key!" : " Dragon Keys!");
      }

      public static function mmHook(param1:String) : String
      {
         if(param1 != null && param1.indexOf(PG_MARK) == 0)
         {
            paragon = int(param1.substr(PG_MARK.length));
            return "";
         }
         if(param1 != null && param1.indexOf(KY_MARK) == 0)
         {
            return mmKeys(uint(param1.substr(KY_MARK.length)));
         }
         if(param1 != null && param1.indexOf(WS_MARK) == 0)
         {
            mmWidescreen(param1.charAt(WS_MARK.length) == "1");
            return param1.charAt(WS_MARK.length) == "1" ? "View: widescreen 16:9" : "View: original 3:2";
         }
         if(param1 == null || param1.indexOf(MM_MARK) != 0)
         {
            return param1;
         }
         try
         {
            mmOpen(param1.substr(MM_MARK.length));
         }
         catch(e:Error)
         {
            return "Mount Merchant: " + e.message;
         }
         return "";
      }

      private static function mmOpen(param1:String) : void
      {
         var _loc2_:Array = param1.split("|");
         var _loc3_:String = null;
         var _loc4_:Array = null;
         mmWallet = {
            "I":Number(_loc2_[1]),
            "S":Number(_loc2_[2]),
            "G":Number(_loc2_[3])
         };
         mmItems = [];
         for each(_loc3_ in String(_loc2_[4]).split(","))
         {
            if(_loc3_)
            {
               _loc4_ = _loc3_.split(":");
               mmItems.push({
                  "id":uint(_loc4_[0]),
                  "cur":String(_loc4_[1]),
                  "price":uint(_loc4_[2]),
                  "owned":_loc4_[3] == "1"
               });
            }
         }
         if(mmSel >= mmItems.length)
         {
            mmSel = 0;
         }
         mmBusy = false;
         if(!mmWin)
         {
            mmBuild();
         }
         mmRefresh();
         mmWin.x = int((Camera.SCREEN_WIDTH - W) / 2);
         SuperAnimData.aaMain.addChild(mmWin);
      }

      private static function mmType(param1:Object) : class_20
      {
         return class_14.var_464[param1.id] as class_20;
      }

      private static function mmIcon(param1:Object, param2:uint) : DisplayObject
      {
         var _loc3_:class_20 = mmType(param1);
         return !!_loc3_ ? class_41.method_168(_loc3_,0,0,param2,param2,SuperAnimData.aaMain.overallScale) : null;
      }

      private static function mmRarityColor(param1:String) : uint
      {
         if(param1 == "L")
         {
            return 0xF8DC45;
         }
         if(param1 == "R")
         {
            return 0x3FA9FF;
         }
         return CREAM;
      }

      private static function mmCurrency(param1:String) : String
      {
         if(param1 == "G")
         {
            return "Gold";
         }
         if(param1 == "S")
         {
            return "Sigils";
         }
         return "Idols";
      }

      private static function mmNumber(param1:Number) : String
      {
         var _loc2_:String = String(Math.floor(param1));
         var _loc3_:String = "";
         while(_loc2_.length > 3)
         {
            _loc3_ = "," + _loc2_.substr(_loc2_.length - 3) + _loc3_;
            _loc2_ = _loc2_.substr(0,_loc2_.length - 3);
         }
         return _loc2_ + _loc3_;
      }

      private static function mmBox(param1:Sprite, param2:Number, param3:Number, param4:Number, param5:Number, param6:uint, param7:uint, param8:Number) : void
      {
         param1.graphics.lineStyle(param8,param7);
         param1.graphics.beginFill(param6);
         param1.graphics.drawRoundRect(param2,param3,param4,param5,18,18);
         param1.graphics.endFill();
      }

      private static function mmText(param1:Sprite, param2:Number, param3:Number, param4:Number, param5:int, param6:uint, param7:Boolean, param8:String = "left", param9:Number = 0) : TextField
      {
         var _loc10_:TextField = new TextField();
         _loc10_.selectable = false;
         _loc10_.mouseEnabled = false;
         _loc10_.defaultTextFormat = new TextFormat("Arial",param5,param6,param7,null,null,null,null,param8);
         _loc10_.x = param2;
         _loc10_.y = param3;
         _loc10_.width = param4;
         _loc10_.multiline = param9 > 0;
         _loc10_.wordWrap = param9 > 0;
         _loc10_.height = param9 > 0 ? param9 : param5 + 10;
         _loc10_.filters = [new DropShadowFilter(1,45,0,1,2,2,1)];
         param1.addChild(_loc10_);
         return _loc10_;
      }

      private static function mmSetText(param1:TextField, param2:String, param3:uint) : void
      {
         var _loc4_:TextFormat = param1.defaultTextFormat;
         _loc4_.color = param3;
         param1.defaultTextFormat = _loc4_;
         param1.text = param2;
      }

      private static function mmButton(param1:Sprite, param2:Number, param3:Number, param4:Number, param5:String, param6:Function) : Sprite
      {
         var _loc7_:Sprite = new Sprite();
         _loc7_.x = param2;
         _loc7_.y = param3;
         _loc7_.name = param5;
         _loc7_.buttonMode = true;
         _loc7_.mouseChildren = false;
         mmText(_loc7_,0,10,param4,20,0xFFFFFF,true,"center");
         _loc7_.addEventListener(MouseEvent.CLICK,param6);
         param1.addChild(_loc7_);
         return _loc7_;
      }

      private static function mmPaintButton(param1:Sprite, param2:Number, param3:uint, param4:String) : void
      {
         param1.graphics.clear();
         param1.graphics.lineStyle(3,0xF0E0A0);
         param1.graphics.beginFill(param3);
         param1.graphics.drawRoundRect(0,0,param2,46,22,22);
         param1.graphics.endFill();
         (param1.getChildAt(0) as TextField).text = param4;
      }

      private static function mmBuild() : void
      {
         var _loc1_:int = 0;
         var _loc2_:Sprite = null;
         mmWin = new Sprite();
         mmWin.y = 70;
         mmWin.filters = [new DropShadowFilter(6,45,0,0.7,12,12,1)];
         mmWin.addEventListener(MouseEvent.MOUSE_DOWN,mmSwallow);
         mmWin.addEventListener(MouseEvent.MOUSE_UP,mmSwallow);
         mmWin.addEventListener(MouseEvent.CLICK,mmSwallow);
         mmBox(mmWin,0,0,W,H,0x2B1D0E,GOLD,6);
         // left: the selected mount, then every mount, a page at a time
         mmBox(mmWin,18,18,592,196,0x1A120A,0x5A4420,2);
         mmPreview = new Sprite();
         mmPreview.x = 314;
         mmPreview.y = 116;
         mmWin.addChild(mmPreview);
         mmBox(mmWin,18,228,592,294,0x3A2812,GOLD,4);
         mmPageText = mmText(mmWin,100,240,428,18,0xFFF2C0,true,"center");
         mmPaintButton(mmButton(mmWin,30,234,60,"prev",mmPrev),60,0x6B4A1A,"<");
         mmPaintButton(mmButton(mmWin,538,234,60,"next",mmNext),60,0x6B4A1A,">");
         mmSlots = [];
         _loc1_ = 0;
         while(_loc1_ < PER_PAGE)
         {
            _loc2_ = new Sprite();
            _loc2_.x = 28 + _loc1_ % 6 * 96;
            _loc2_.y = 286 + int(_loc1_ / 6) * 118;
            _loc2_.name = String(_loc1_);
            _loc2_.buttonMode = true;
            _loc2_.mouseChildren = false;
            _loc2_.addEventListener(MouseEvent.CLICK,mmSelect);
            mmWin.addChild(_loc2_);
            mmSlots.push(_loc2_);
            _loc1_++;
         }
         // right: details
         mmBox(mmWin,628,18,314,504,0x3A2812,GOLD,4);
         mmBox(mmWin,644,32,282,40,0x24180B,0x5A4420,2);
         mmText(mmWin,644,38,282,24,CREAM,true,"center").text = "MOUNT MERCHANT";
         mmBox(mmWin,644,84,282,74,0x24180B,0x5A4420,2);
         mmText(mmWin,644,92,282,16,CREAM,true,"center").text = "Your stable";
         mmOwned = mmText(mmWin,644,114,282,22,CREAM,true,"center");
         mmBox(mmWin,644,170,282,338,0x24180B,0x5A4420,2);
         mmRarity = mmText(mmWin,650,180,270,14,CREAM,true,"center");
         mmName = mmText(mmWin,650,198,270,24,CREAM,true,"center",64);
         mmDesc = mmText(mmWin,656,262,258,14,CREAM,false,"center",84);
         mmText(mmWin,650,350,270,18,CREAM,true,"center").text = "Price";
         mmPrice = mmText(mmWin,650,374,270,24,CREAM,true,"center");
         mmYours = mmText(mmWin,650,412,270,15,CREAM,true,"center");
         mmPaintButton(mmButton(mmWin,656,450,110,"done",mmClose),110,0x1E78D8,"DONE");
         mmBuy = mmButton(mmWin,778,450,136,"buy",mmBuyClick);
      }

      private static function mmRefresh() : void
      {
         var _loc1_:int = 0;
         var _loc2_:Sprite = null;
         var _loc3_:Object = null;
         var _loc4_:class_20 = null;
         var _loc5_:DisplayObject = null;
         var _loc6_:Boolean = false;
         var _loc7_:int = 0;
         var _loc8_:int = 0;
         var _loc9_:int = Math.max(1,Math.ceil(mmItems.length / PER_PAGE));
         mmPage = Math.max(0,Math.min(mmPage,_loc9_ - 1));
         for each(_loc3_ in mmItems)
         {
            if(_loc3_.owned)
            {
               _loc8_++;
            }
         }
         mmOwned.text = _loc8_ + " of " + mmItems.length + " mounts";
         mmPageText.text = "MOUNTS   " + (mmPage + 1) + " / " + _loc9_;
         _loc1_ = 0;
         while(_loc1_ < mmSlots.length)
         {
            _loc2_ = mmSlots[_loc1_];
            while(_loc2_.numChildren)
            {
               _loc2_.removeChildAt(0);
            }
            _loc2_.graphics.clear();
            _loc7_ = mmPage * PER_PAGE + _loc1_;
            _loc3_ = mmItems[_loc7_];
            _loc2_.visible = _loc3_ != null;
            if(_loc3_)
            {
               _loc4_ = mmType(_loc3_);
               mmBox(_loc2_,0,0,88,112,_loc7_ == mmSel ? 0x5A3E14 : 0x2B1D0E,_loc7_ == mmSel ? 0xFFE27A : 0x5A4420,_loc7_ == mmSel ? 3 : 2);
               mmBox(_loc2_,16,6,56,56,0x1A120A,GOLD,2);
               _loc5_ = mmIcon(_loc3_,52);
               if(_loc5_)
               {
                  _loc5_.x = 18;
                  _loc5_.y = 8;
                  _loc2_.addChild(_loc5_);
               }
               mmText(_loc2_,2,63,84,11,mmRarityColor(!!_loc4_ ? _loc4_.var_255 : "M"),true,"center",30).text = !!_loc4_ ? _loc4_.displayName : "Mount " + _loc3_.id;
               _loc6_ = mmWallet[_loc3_.cur] >= _loc3_.price;
               if(_loc3_.owned)
               {
                  mmText(_loc2_,2,92,84,11,GREEN,true,"center").text = "OWNED";
               }
               else
               {
                  mmText(_loc2_,2,92,84,11,_loc6_ ? CREAM : RED,true,"center").text = mmNumber(_loc3_.price) + " " + mmCurrency(_loc3_.cur);
               }
            }
            _loc1_++;
         }
         mmShowSelected();
      }

      private static function mmShowSelected() : void
      {
         var _loc1_:Object = mmItems[mmSel];
         var _loc2_:class_20 = !!_loc1_ ? mmType(_loc1_) : null;
         var _loc3_:DisplayObject = null;
         var _loc4_:String = null;
         var _loc5_:Boolean = false;
         while(mmPreview.numChildren)
         {
            mmPreview.removeChildAt(0);
         }
         if(!_loc1_)
         {
            mmSetText(mmName,"Sold out",CREAM);
            mmRarity.text = mmDesc.text = mmPrice.text = mmYours.text = "";
            mmPaintButton(mmBuy,136,0x6A6A6A,"BUY MOUNT");
            return;
         }
         _loc3_ = mmIcon(_loc1_,170);
         if(_loc3_)
         {
            _loc3_.x = -85;
            _loc3_.y = -85;
            _loc3_.filters = [new GlowFilter(0,0.6,10,10,2)];
            mmPreview.addChild(_loc3_);
         }
         _loc4_ = !!_loc2_ ? _loc2_.var_255 : "M";
         mmSetText(mmRarity,_loc4_ == "L" ? "LEGENDARY MOUNT" : (_loc4_ == "R" ? "RARE MOUNT" : "MAGIC MOUNT"),CREAM);
         mmSetText(mmName,!!_loc2_ ? _loc2_.displayName : "Mount " + _loc1_.id,mmRarityColor(_loc4_));
         mmDesc.text = !!_loc2_ && _loc2_.description ? _loc2_.description : "";
         _loc5_ = mmWallet[_loc1_.cur] >= _loc1_.price;
         mmSetText(mmPrice,mmNumber(_loc1_.price) + " " + mmCurrency(_loc1_.cur),_loc1_.owned || _loc5_ ? 0xFFE27A : RED);
         mmYours.text = "YOUR " + mmCurrency(_loc1_.cur).toUpperCase() + ":   " + mmNumber(mmWallet[_loc1_.cur]);
         if(_loc1_.owned)
         {
            mmPaintButton(mmBuy,136,0x3E8E2E,"OWNED");
         }
         else if(mmBusy)
         {
            mmPaintButton(mmBuy,136,0x6A6A6A,"...");
         }
         else
         {
            mmPaintButton(mmBuy,136,_loc5_ ? 0xD08A10 : 0x6A6A6A,"BUY MOUNT");
         }
      }

      private static function mmPrev(param1:MouseEvent) : void
      {
         param1.stopPropagation();
         mmPage--;
         mmRefresh();
      }

      private static function mmNext(param1:MouseEvent) : void
      {
         param1.stopPropagation();
         mmPage++;
         mmRefresh();
      }

      private static function mmSwallow(param1:MouseEvent) : void
      {
         param1.stopPropagation();
      }

      private static function mmSelect(param1:MouseEvent) : void
      {
         param1.stopPropagation();
         mmSel = mmPage * PER_PAGE + int((param1.currentTarget as Sprite).name);
         mmRefresh();
      }

      private static function mmClose(param1:MouseEvent) : void
      {
         param1.stopPropagation();
         if(mmWin && mmWin.parent)
         {
            mmWin.parent.removeChild(mmWin);
         }
      }

      private static function mmBuyClick(param1:MouseEvent) : void
      {
         var _loc2_:Object = mmItems[mmSel];
         var _loc3_:Game = SuperAnimData.aaMain.var_523[0];
         param1.stopPropagation();
         if(!_loc2_ || _loc2_.owned || mmBusy || mmWallet[_loc2_.cur] < _loc2_.price || !_loc3_)
         {
            return;
         }
         mmBusy = true;
         mmShowSelected();
         _loc3_.linkUpdater.WriteChatMessage(_loc3_.clientEntID,"!mmbuy " + _loc2_.id);
      }
   }
}
