from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables
import anvil.users
import datetime
from TimerForm import TimerForm
import parameters as p

class Form1(Form1Template):
  current_status = None
  user_id = None
  seconds_left = None
  trust_level = 0
  tallies =	dict(requesting = 0,
                 offering = 0,
                 request_em = 0)
  def __init__(self, **properties):
    # You must call self.init_components() before doing anything else in this function
    self.init_components(**properties)
    
    self.user_id = anvil.users.get_user().get_id()
    # 'prune' initializes new users to trust level 0 (via 'get_trust_level')
    t, r, m, s, ref_time, n, alt_avail, e = anvil.server.call('prune',self.user_id)
    if e==False:
      alert('Your email address is not approved to use this app. '
            + 'Contact empathyroom@gmail.com for help.')
      self.logout_user()
    self.trust_level = t
    self.request_em_check_box.checked = r
    self.match_em_check_box.checked = m
    self.tallies = n
    self.current_status = s
    if self.current_status == "matched":
      timer = datetime.datetime.now(ref_time.tzinfo) - ref_time
      if alt_avail:
        self.seconds_left = p.CONFIRM_MATCH_SECONDS + p.BUFFER_SECONDS - timer.seconds
      else:
        self.seconds_left = p.CONFIRM_WAIT_SECONDS + p.BUFFER_SECONDS - timer.seconds
      if self.seconds_left<=0:
        self.current_status = anvil.server.call('cancel_other',self.user_id)
    elif self.current_status == "pinged":
      if alt_avail:
        timer = datetime.datetime.now(ref_time.tzinfo) - ref_time
        self.seconds_left = p.CONFIRM_MATCH_SECONDS - timer.seconds
      else:
        self.seconds_left = p.CONFIRM_WAIT_SECONDS
      if self.seconds_left<=0:
        anvil.server.call('cancel',self.user_id)
        self.current_status = None
      else:
        self.confirm_match()
        ## Old code for asking whether recent match still ongoing
        # conditional on status "empathy"
        #ongoing = confirm("Is your empathy session, begun "
        #                  + str(timer.seconds/60)
        #                  + " minutes ago, still ongoing?")
        #  if ongoing:
        #    self.current_status = "empathy"
        #  else:
        #    self.current_status = None
        #    anvil.server.call('match_complete',self.user_id)
    self.set_form_status(self.current_status)
    
  def request_button_click(self, **event_args):
    """This method is called when the button is clicked"""
    if self.drop_down_1.selected_value=="Not ready to offer empathy first":
      request_type = 'requesting'
    else:
      request_type = 'offering'
    jitsi_code, last_confirmed, num_emailed = anvil.server.call('add_request',
                                                                self.user_id,
                                                                request_type)
    if jitsi_code == None:
      if num_emailed > 0:
        if num_emailed==1:
          n = Notification('Someone has been sent a '
                           + 'notification email about your request.',
                           title='Email notification sent',
                           timeout=10)
        else:
          n = Notification(str(num_emailed) + ' others have been sent '
                           + 'notification emails about your request.',
                           title='Email notifications sent',
                           timeout=10)
        n.show()
      self.current_status = request_type
    else:
      timer = datetime.datetime.now(last_confirmed.tzinfo) - last_confirmed
      if timer.seconds > p.CONFIRM_MATCH_SECONDS:
        self.current_status = "matched"
        self.seconds_left = p.CONFIRM_MATCH_SECONDS + p.BUFFER_SECONDS
      else:
        self.current_status = "empathy"
    self.set_form_status(self.current_status) 

  def timer_1_tick(self, **event_args):
    """This method is called Every 5 seconds"""
    if self.current_status in ["requesting", "offering"]:
      new_status, ref_time, n, alt_avail = anvil.server.call_s('get_status',self.user_id)
      if new_status == "pinged":
        if self.match_em_check_box.checked:
          anvil.server.call('match_email')
        self.current_status = new_status
        if alt_avail:
          self.seconds_left = p.CONFIRM_MATCH_SECONDS
        self.confirm_match()
      elif new_status in ["empathy", None]:
        self.current_status = new_status
        self.tallies = n
        self.set_form_status(self.current_status)
      elif new_status != self.current_status:
        print new_status
    elif self.current_status == "matched":
      new_status, ref_time, n, alt_avail = anvil.server.call_s('get_status',self.user_id)
      if new_status == "requesting":
        alert("The empathy offer was canceled.")
        self.current_status = new_status
        self.set_form_status(self.current_status)
      elif new_status == "offering":
        alert("The empathy request was canceled.")
        self.current_status = new_status
        self.set_form_status(self.current_status)
      elif new_status in ["empathy", None]:
        self.current_status = new_status
        self.tallies = n
        self.set_form_status(self.current_status)
      elif new_status != self.current_status:
        print new_status
      else:
        timer = datetime.datetime.now(ref_time.tzinfo) - ref_time
        if alt_avail:
          self.seconds_left = p.CONFIRM_MATCH_SECONDS + p.BUFFER_SECONDS - timer.seconds
        else:
          self.seconds_left = p.CONFIRM_WAIT_SECONDS + p.BUFFER_SECONDS - timer.seconds
    elif self.current_status == None:
      self.tallies = anvil.server.call_s('get_tallies')
      self.update_tally_label()

  def timer_2_tick(self, **event_args):
    """This method is called Every 1 seconds"""
    if self.current_status in ["requesting", "offering"]:
      self.seconds_left -= 1
      if self.seconds_left<=0:
        self.confirm_wait()
    elif self.current_status == "matched":
      self.seconds_left -= 1
      self.timer_label.text = ("A match has been found and they have up to " 
                               + str(self.seconds_left) + " seconds to confirm.")
      if self.seconds_left<=0:
        self.current_status = anvil.server.call('cancel_other',self.user_id)
        self.set_form_status(self.current_status)
    
  def cancel_button_click(self, **event_args):
    """This method is called when the button is clicked"""
    self.current_status = None
    anvil.server.call('cancel',self.user_id)
    self.set_form_status(self.current_status)

  def complete_button_click(self, **event_args):
    """This method is called when the button is clicked"""
    self.current_status = None
    anvil.server.call('match_complete',self.user_id)
    self.set_form_status(self.current_status)

    
  def set_form_status(self, user_status):
    if user_status:
      self.request_button.visible = False
      self.drop_down_1.enabled = False
      self.drop_down_1.foreground = "gray"
      self.tally_label.visible = False
      if user_status in ["requesting","offering"]:
        self.status.text = ("Status: Requesting an empathy exchange. "
                            + "(Note: Your request will be cancelled after "
                            + str(2*p.CONFIRM_WAIT_SECONDS/60)
                            + " minutes of inactivity. After "
                            + str(p.CONFIRM_WAIT_SECONDS/60)
                            + " minutes, a dialog will appear allowing "
                            + "you to refresh your request.)")
        self.status.bold = False
        self.set_jitsi_link("")
        self.complete_button.visible = False
        self.cancel_button.visible = True
        self.set_drop_down(user_status)
        self.seconds_left = p.CONFIRM_WAIT_SECONDS
        self.match_em_check_box.visible = True
      else:
        assert user_status in ["matched", "empathy"]
        self.cancel_button.visible = False        
        if user_status=="matched":
          self.timer_label.text = ("A match has been found and they have up to " 
                                   + str(self.seconds_left) + " seconds to confirm.")
          self.timer_label.visible = True
          self.status.text = "A match should be ready soon. Set up Jitsi at: "
          self.status.bold = False
          jitsi_code, request_type = anvil.server.call('get_code', self.user_id)
          self.complete_button.visible = False
        else:
          assert user_status=="empathy"
          self.timer_label.visible = False
          (new_status, match_start,  
           jitsi_code, request_type) = anvil.server.call('match_commenced',
                                                         self.user_id)
          if new_status != "empathy":
            assert new_status != "matched"
            self.current_status = new_status
            return self.set_form_status(self.current_status)
          self.status.text = "You have a confirmed match. Use Jitsi to meet: "
          self.status.bold = True
          self.complete_button.visible = True
        self.set_jitsi_link(jitsi_code)     
        self.set_drop_down(request_type)
        self.match_em_check_box.visible = False
    else:
      self.status.text = "Request a match when ready:"
      self.status.bold = True
      self.set_jitsi_link("")
      self.timer_label.visible = False
      self.complete_button.visible = False
      self.cancel_button.visible = False
      self.request_button.visible = True
      self.drop_down_1.enabled = True
      self.drop_down_1.foreground = "black"
      self.match_em_check_box.visible = False
      self.update_tally_label()
      

  def update_tally_label(self):
    temp = ""
    if self.tallies['requesting'] > 1:
      if self.tallies['offering'] > 0:
        temp = (str(self.tallies['requesting'] + self.tallies['offering'])
                + ' current requests for an empathy exchange, '
                + 'some of which are requesting a partner willing to offer empathy first.')
      else:
        assert self.tallies['offering']==0
        temp = (str(self.tallies['requesting'])
                + ' current requests for an empathy exchange, '
                + 'all of which are requesting a partner willing to offer empathy first.')
    elif self.tallies['requesting']==1:
      if self.tallies['offering'] > 0:
        temp = (str(self.tallies['requesting'] + self.tallies['offering'])
                + ' current requests for an empathy exchange. '
                + 'One is requesting a partner willing to offer empathy first.')
      else:
        assert self.tallies['offering']==0
        temp = (str(self.tallies['requesting'])
                + ' current request for an empathy exchange, '
                + 'requesting a partner willing to offer empathy first.')
    else:
      assert self.tallies['requesting']==0
      if self.tallies['offering'] > 1:
        temp = (str(self.tallies['offering'])
                + ' current requests for an empathy exchange, '
                + 'all of which are willing to offer empathy first.') 
      elif self.tallies['offering']==1:
        temp = (str(self.tallies['offering'])
                + ' current request for an empathy exchange '
                + 'by someone willing to offer empathy first.')
      else:
        assert self.tallies['offering']==0
    if self.tallies['offering']==0:
      if self.tallies['requesting'] > 0:
        if self.tallies['request_em'] > 1:
          temp += (str(self.tallies['request_em'])
                   + ' others are currently receiving email notifications '
                   + 'about each request for empathy.')
        elif self.tallies['request_em']==1:
          temp += (str(self.tallies['request_em'])
                   + ' other person is currently receiving email notifications '
                   + 'about each request for empathy.')
      else:
        if self.tallies['request_em'] > 1:
          temp += (str(self.tallies['request_em'])
                   + ' people are currently receiving email notifications '
                   + 'about each request for empathy.')
        elif self.tallies['request_em']==1:
          temp += (str(self.tallies['request_em'])
                   + ' person is currently receiving email notifications '
                   + 'about each request for empathy.')
    self.tally_label.text = temp
    if len(temp) > 0:
      self.tally_label.visible = True
      
  def set_jitsi_link(self, jitsi_code):
    if jitsi_code == "":
      self.jitsi_link.visible = False
      self.jitsi_link.text = ""
      self.jitsi_link.url = ""
    else:
      self.jitsi_link.url = "https://meet.jit.si/" + jitsi_code
      self.jitsi_link.text = self.jitsi_link.url
      self.jitsi_link.visible = True
    
  def confirm_match(self):
    assert self.current_status=="pinged"
    f = TimerForm(self.seconds_left, self.user_id, self.current_status)
    out = confirm(content=f,
                  title="A match is available. Are you ready?",
                  large=False,
                  dismissible=False)
    if out==True:
      self.current_status = "empathy"
    elif out==False:
      anvil.server.call('cancel',self.user_id)
      self.current_status = None
    elif out=="timer elapsed":
      anvil.server.call('cancel',self.user_id)
      self.current_status = None
      alert("A match was found, but the time available for you to confirm ("
            + str(p.CONFIRM_MATCH_SECONDS) + ") has elapsed.",
            dismissible=False)
    else:
      print out
      assert out in [None,"requesting","offering"]
      self.current_status = out
    self.set_form_status(self.current_status)
    
    #open_form('ConfirmForm', self.seconds_left, self.user_id,
    #          "A match is available. Are you ready?")

  def confirm_wait(self):
    assert self.current_status in ["requesting", "offering"]
    f = TimerForm(p.CONFIRM_WAIT_SECONDS, self.user_id, self.current_status)
    out = confirm(content=f,
                  title="Continue waiting for a match?",
                  large=False,
                  dismissible=False)
    if out==True:
      anvil.server.call('confirm_wait',self.user_id)
      #seconds_left reset by set_form_status() below
    elif out==False:
      anvil.server.call('cancel',self.user_id)
      self.current_status = None
    elif out=="timer elapsed":
      anvil.server.call('cancel',self.user_id)
      self.current_status = None
      alert("Request canceled due to failure to confirm within "
            + str(p.CONFIRM_WAIT_SECONDS) + " seconds.",
            dismissible=False)
    else:
      print out
      assert out in ["pinged","empathy"]
      self.current_status = out
      if out=="pinged":
        self.seconds_left = p.CONFIRM_MATCH_SECONDS
        self.confirm_match()
    self.set_form_status(self.current_status)

  def set_drop_down(self, request_type):
    if request_type=="requesting":
      self.drop_down_1.selected_value = "Not ready to offer empathy first"
    else:
      assert request_type=="offering"
      self.drop_down_1.selected_value = "Willing to offer empathy first"
 
  def logout_button_click(self, **event_args):
    """This method is called when the button is clicked"""
    self.logout_user()

  def logout_user(self):  
    anvil.users.logout()
    self.set_form_status(None)
    self.user_id = None
    open_form('LoginForm')
       
  def match_em_check_box_change(self, **event_args):
    """This method is called when this checkbox is checked or unchecked"""
    anvil.server.call('set_match_em', self.match_em_check_box.checked)

  def request_em_check_box_change(self, **event_args):
    """This method is called when this checkbox is checked or unchecked"""
    anvil.server.call('set_request_em', self.request_em_check_box.checked)





